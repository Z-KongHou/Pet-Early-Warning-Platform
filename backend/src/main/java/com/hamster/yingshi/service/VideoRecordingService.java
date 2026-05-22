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

    // cameraId -> FFmpeg process, 用于跟踪正在录制的进程
    private final Map<Integer, Process> activeRecordings = new ConcurrentHashMap<>();

    @Scheduled(fixedDelayString = "${recording.duration-seconds:60}000")
    public void recordAllCameras() {
        if (!recordingProperties.isEnabled()) {
            return;
        }

        List<Camera> cameras;
        try {
            cameras = cameraService.findAll();
        } catch (Exception e) {
            log.error("获取摄像头列表失败", e);
            return;
        }

        for (Camera camera : cameras) {
            try {
                recordCamera(camera);
            } catch (Exception e) {
                log.error("录制摄像头 {} 失败: {}", camera.getId(), e.getMessage());
            }
        }
    }

    private void recordCamera(Camera camera) {
        int cameraId = camera.getId();
        int duration = recordingProperties.getDurationSeconds();

        // 如果该摄像头已有录制进程在运行，跳过
        Process existing = activeRecordings.get(cameraId);
        if (existing != null && existing.isAlive()) {
            log.debug("摄像头 {} 正在录制中，跳过", cameraId);
            return;
        }

        // 获取直播流地址
        String streamUrl;
        try {
            streamUrl = ezvizService.getLiveStreamUrlWithRetry(camera);
        } catch (Exception e) {
            log.warn("获取摄像头 {} 直播地址失败: {}", cameraId, e.getMessage());
            return;
        }

        // 构建输出路径: video/{cameraId}/{date}/{startTime}-{endTime}.mp4
        LocalDateTime now = LocalDateTime.now();
        String dateDir = now.format(DATE_FMT);
        String startTimeStr = now.format(TIME_FMT);
        LocalDateTime endTime = now.plusSeconds(duration);
        String endTimeStr = endTime.format(TIME_FMT);

        String storagePath = recordingProperties.getStoragePath();
        File outputDir = new File(storagePath, cameraId + "/" + dateDir);
        if (!outputDir.exists() && !outputDir.mkdirs()) {
            log.error("创建录制目录失败: {}", outputDir.getAbsolutePath());
            return;
        }

        String fileName = startTimeStr + "-" + endTimeStr + ".mp4";
        File outputFile = new File(outputDir, fileName);

        // 构建 FFmpeg 命令
        String ffmpegPath = recordingProperties.getFfmpegPath();
        ProcessBuilder pb = new ProcessBuilder(
                ffmpegPath,
                "-y",                          // 覆盖已有文件
                "-i", streamUrl,               // 输入流
                "-t", String.valueOf(duration), // 录制时长(秒)
                "-c", "copy",                  // 直接复制编码，不转码
                "-f", "mp4",                   // 输出格式
                outputFile.getAbsolutePath()
        );
        pb.redirectErrorStream(true);

        try {
            log.info("开始录制摄像头 {}: {} -> {}", cameraId, streamUrl, outputFile.getAbsolutePath());
            Process process = pb.start();
            activeRecordings.put(cameraId, process);

            // 异步等待进程结束
            new Thread(() -> {
                try {
                    int exitCode = process.waitFor();
                    activeRecordings.remove(cameraId);
                    if (exitCode == 0) {
                        log.info("录制完成: {}", outputFile.getAbsolutePath());
                    } else {
                        log.warn("录制异常退出(exitCode={}): {}", exitCode, outputFile.getAbsolutePath());
                        // 删除不完整的文件
                        if (outputFile.exists()) {
                            outputFile.delete();
                        }
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }, "recorder-" + cameraId).start();

        } catch (IOException e) {
            log.error("启动 FFmpeg 失败: {}", e.getMessage());
            activeRecordings.remove(cameraId);
        }
    }

    /**
     * 停止指定摄像头的录制
     */
    public void stopRecording(Integer cameraId) {
        Process process = activeRecordings.remove(cameraId);
        if (process != null && process.isAlive()) {
            process.destroy();
            log.info("已停止摄像头 {} 的录制", cameraId);
        }
    }

    /**
     * 停止所有录制
     */
    public void stopAllRecordings() {
        activeRecordings.forEach((cameraId, process) -> {
            if (process.isAlive()) {
                process.destroy();
            }
        });
        activeRecordings.clear();
        log.info("已停止所有录制");
    }

    /**
     * 获取指定摄像头指定日期的录像文件列表
     */
    public File[] getRecordings(Integer cameraId, String date) {
        String storagePath = recordingProperties.getStoragePath();
        File dateDir = new File(storagePath, cameraId + "/" + date);
        if (!dateDir.exists() || !dateDir.isDirectory()) {
            return new File[0];
        }
        File[] files = dateDir.listFiles((dir, name) -> name.endsWith(".mp4"));
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
}
