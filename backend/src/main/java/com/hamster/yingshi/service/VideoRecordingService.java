package com.hamster.yingshi.service;

import com.hamster.yingshi.config.RecordingProperties;
import com.hamster.yingshi.entity.Camera;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.io.File;
import java.io.IOException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class VideoRecordingService {

    private static final Logger log = LoggerFactory.getLogger(VideoRecordingService.class);
    private static final DateTimeFormatter DATE_FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd");
    private static final DateTimeFormatter TIME_FMT = DateTimeFormatter.ofPattern("HH-mm-ss");

    @Autowired
    private RecordingProperties recordingProperties;

    @Autowired
    private CameraService cameraService;

    @Autowired
    private EzvizService ezvizService;

    // 录制任务信息
    private static class RecordingTask {
        final Process process;
        final LocalDateTime startTime;
        final File tempFile;
        final File outputDir;

        RecordingTask(Process process, LocalDateTime startTime, File tempFile, File outputDir) {
            this.process = process;
            this.startTime = startTime;
            this.tempFile = tempFile;
            this.outputDir = outputDir;
        }
    }

    // cameraId -> RecordingTask, 用于跟踪正在录制的进程
    private final Map<Integer, RecordingTask> activeRecordings = new ConcurrentHashMap<>();

    @Scheduled(fixedDelayString = "${recording.duration-seconds:300}000")
    public void recordAllCameras() {
        if (!recordingProperties.isEnabled()) {
            return;
        }

        List<Camera> cameras;
        try {
            cameras = cameraService.findAll();
        } catch (Exception e) {
            log.error("Failed to load camera list", e);
            return;
        }

        for (Camera camera : cameras) {
            try {
                recordCamera(camera);
            } catch (Exception e) {
                log.error("Failed to record camera {}: {}", camera.getId(), e.getMessage());
            }
        }
    }

    private void recordCamera(Camera camera) {
        int cameraId = camera.getId();

        // 检查该摄像头是否启用了录像
        if (camera.getRecordingEnabled() == null || camera.getRecordingEnabled() != 1) {
            return;
        }

        int duration = recordingProperties.getDurationSeconds();

        // 如果该摄像头已有录制进程在运行，跳过
        RecordingTask existing = activeRecordings.get(cameraId);
        if (existing != null && existing.process.isAlive()) {
            log.debug("Camera {} is already recording, skip", cameraId);
            return;
        }

        // 获取直播流地址
        String streamUrl;
        try {
            streamUrl = ezvizService.getLiveStreamUrlWithRetry(camera);
        } catch (Exception e) {
            log.warn("Failed to get live stream URL for camera {}: {}", cameraId, e.getMessage());
            return;
        }

        // 构建输出路径: video/{cameraId}/{date}/
        LocalDateTime startTime = LocalDateTime.now();
        String dateDir = startTime.format(DATE_FMT);
        String startTimeStr = startTime.format(TIME_FMT);

        String storagePath = recordingProperties.getStoragePath();
        File outputDir = new File(storagePath, cameraId + "/" + dateDir);
        if (!outputDir.exists() && !outputDir.mkdirs()) {
            log.error("Failed to create recording directory: {}", outputDir.getAbsolutePath());
            return;
        }

        // 使用临时文件名录制，结束后根据实际时长重命名
        File tempFile = new File(outputDir, startTimeStr + "-recording.mp4");

        // 构建 FFmpeg 命令（转码为标准 H.264，确保 MP4 兼容性）
        String ffmpegPath = recordingProperties.getFfmpegPath();
        ProcessBuilder pb = new ProcessBuilder(
                ffmpegPath,
                "-y",                          // 覆盖已有文件
                "-fflags", "+genpts",           // 为直播流生成 PTS 时间戳
                "-i", streamUrl,               // 输入流
                "-t", String.valueOf(duration), // 录制时长(秒)
                "-c:v", "libx264",             // 转码为 H.264
                "-preset", "ultrafast",         // 最快编码速度，降低 CPU 占用
                "-crf", "28",                  // 画质(18-28为合理范围，28偏高压缩)
                "-c:a", "aac",                 // 音频编码为 AAC
                "-movflags", "+faststart",     // 将 moov atom 放到文件头部
                "-f", "mp4",                   // 输出格式
                tempFile.getAbsolutePath()
        );
        pb.redirectErrorStream(true);

        try {
            log.info("Started recording camera {}: {} -> {}", cameraId, streamUrl, tempFile.getAbsolutePath());
            Process process = pb.start();
            activeRecordings.put(cameraId, new RecordingTask(process, startTime, tempFile, outputDir));

            // 异步读取 FFmpeg 输出并等待进程结束
            new Thread(() -> {
                try (var reader = new java.io.BufferedReader(new java.io.InputStreamReader(process.getInputStream()))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        log.debug("[ffmpeg-{}] {}", cameraId, line);
                    }
                } catch (IOException ignored) {
                }
                try {
                    int exitCode = process.waitFor();
                    activeRecordings.remove(cameraId);
                    if (tempFile.exists() && tempFile.length() > 0) {
                        // 无论退出码如何，只要文件有内容就重命名保存
                        renameToFinal(tempFile, outputDir, startTime);
                    } else {
                        log.warn("Recording exited abnormally (exitCode={}, fileSize={}): {}",
                                exitCode, tempFile.length(), tempFile.getAbsolutePath());
                        if (tempFile.exists() && tempFile.length() == 0) {
                            tempFile.delete();
                        }
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }, "recorder-" + cameraId).start();

        } catch (IOException e) {
            log.error("Failed to start FFmpeg: {}", e.getMessage());
            activeRecordings.remove(cameraId);
        }
    }

    /**
     * 根据实际录制时长重命名临时文件为最终文件名
     */
    private void renameToFinal(File tempFile, File outputDir, LocalDateTime startTime) {
        long durationMs = java.time.Duration.between(startTime, LocalDateTime.now()).toMillis();
        long durationSec = Math.max(1, durationMs / 1000); // 至少1秒
        LocalDateTime endTime = startTime.plusSeconds(durationSec);
        String startTimeStr = startTime.format(TIME_FMT);
        String endTimeStr = endTime.format(TIME_FMT);
        String finalName = startTimeStr + "-" + endTimeStr + ".mp4";
        File finalFile = new File(outputDir, finalName);
        if (tempFile.renameTo(finalFile)) {
            log.info("Recording finished: {} ({}KB, duration={}s)", finalFile.getAbsolutePath(), finalFile.length() / 1024, durationSec);
        } else {
            log.warn("Failed to rename file: {} -> {}", tempFile.getAbsolutePath(), finalFile.getAbsolutePath());
        }
    }

    /**
     * 停止指定摄像头的录制
     */
    public void stopRecording(Integer cameraId) {
        RecordingTask task = activeRecordings.remove(cameraId);
        if (task == null) return;

        // 如果进程还在运行，先停止它
        if (task.process.isAlive()) {
            task.process.destroy(); // 发送 SIGTERM，FFmpeg 会自动保存已录制部分
            // 等待进程结束，确保 FFmpeg 将缓冲区写入文件
            try {
                task.process.waitFor(5, java.util.concurrent.TimeUnit.SECONDS);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
        }

        // 无论进程是否还在运行，只要临时文件存在就重命名
        if (task.tempFile.exists() && task.tempFile.length() > 0) {
            renameToFinal(task.tempFile, task.outputDir, task.startTime);
        }
        log.info("Stopped recording for camera {}", cameraId);
    }

    /**
     * 停止所有录制（等待进程结束以确保文件保存完整）
     */
    public void stopAllRecordings() {
        // 先停止所有运行中的进程
        activeRecordings.forEach((cameraId, task) -> {
            if (task.process.isAlive()) {
                task.process.destroy();
            }
        });
        // 等待所有进程结束，确保 FFmpeg 将缓冲区写入文件
        activeRecordings.forEach((cameraId, task) -> {
            try {
                task.process.waitFor(5, java.util.concurrent.TimeUnit.SECONDS);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
        });
        // 重命名所有临时文件
        activeRecordings.forEach((cameraId, task) -> {
            if (task.tempFile.exists() && task.tempFile.length() > 0) {
                renameToFinal(task.tempFile, task.outputDir, task.startTime);
            }
        });
        activeRecordings.clear();
        log.info("Stopped all recordings");
    }

    /**
     * 获取指定摄像头指定日期的录像文件列表（排除正在录制的临时文件）
     */
    public File[] getRecordings(Integer cameraId, String date) {
        String storagePath = recordingProperties.getStoragePath();
        File dateDir = new File(storagePath, cameraId + "/" + date);
        if (!dateDir.exists() || !dateDir.isDirectory()) {
            return new File[0];
        }
        File[] files = dateDir.listFiles((dir, name) -> name.endsWith(".mp4") && !name.endsWith("-recording.mp4"));
        return files != null ? files : new File[0];
    }

    /**
     * 获取指定摄像头指定日期指定文件的录像文件
     */
    public File getRecordingFile(Integer cameraId, String date, String fileName) {
        String storagePath = recordingProperties.getStoragePath();
        File file = new File(storagePath, cameraId + "/" + date + "/" + fileName);
        if (file.exists() && file.getName().endsWith(".mp4")) {
            return file;
        }
        return null;
    }

    /**
     * 删除指定摄像头指定日期指定文件的录像
     * @return true 删除成功，false 文件不存在
     */
    public boolean deleteRecording(Integer cameraId, String date, String fileName) {
        File file = getRecordingFile(cameraId, date, fileName);
        if (file == null) {
            return false;
        }
        return file.delete();
    }
}
