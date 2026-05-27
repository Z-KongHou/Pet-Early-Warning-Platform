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

    // Recording task metadata
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

    // cameraId -> RecordingTask, tracks active recording processes
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

        // Skip if recording is disabled for this camera
        if (camera.getRecordingEnabled() == null || camera.getRecordingEnabled() != 1) {
            return;
        }

        int duration = recordingProperties.getDurationSeconds();

        // Skip if a recording process is already running for this camera
        RecordingTask existing = activeRecordings.get(cameraId);
        if (existing != null && existing.process.isAlive()) {
            log.debug("Camera {} is already recording, skip", cameraId);
            return;
        }

        // Fetch live stream URL
        String streamUrl;
        try {
            streamUrl = ezvizService.getLiveStreamUrlWithRetry(camera);
        } catch (Exception e) {
            log.warn("Failed to get live stream URL for camera {}: {}", cameraId, e.getMessage());
            return;
        }

        // Build output path: video/{cameraId}/{date}/
        LocalDateTime startTime = LocalDateTime.now();
        String dateDir = startTime.format(DATE_FMT);
        String startTimeStr = startTime.format(TIME_FMT);

        String storagePath = recordingProperties.getStoragePath();
        File outputDir = new File(storagePath, cameraId + "/" + dateDir);
        if (!outputDir.exists() && !outputDir.mkdirs()) {
            log.error("Failed to create recording directory: {}", outputDir.getAbsolutePath());
            return;
        }

        // Record to a temp file, then rename based on actual duration when finished
        File tempFile = new File(outputDir, startTimeStr + "-recording.mp4");

        // Build FFmpeg command (transcode to standard H.264 for MP4 compatibility)
        String ffmpegPath = recordingProperties.getFfmpegPath();
        ProcessBuilder pb = new ProcessBuilder(
                ffmpegPath,
                "-y",                          // overwrite existing file
                "-fflags", "+genpts",           // generate PTS timestamps for live stream
                "-i", streamUrl,               // input stream
                "-t", String.valueOf(duration), // recording duration (seconds)
                "-c:v", "libx264",             // transcode to H.264
                "-preset", "ultrafast",         // fastest encoding, lower CPU usage
                "-crf", "28",                  // quality (18-28 is reasonable; 28 is higher compression)
                "-c:a", "aac",                 // encode audio as AAC
                "-movflags", "+faststart",     // place moov atom at file head
                "-f", "mp4",                   // output format
                tempFile.getAbsolutePath()
        );
        pb.redirectErrorStream(true);

        try {
            log.info("Started recording camera {}: {} -> {}", cameraId, streamUrl, tempFile.getAbsolutePath());
            Process process = pb.start();
            activeRecordings.put(cameraId, new RecordingTask(process, startTime, tempFile, outputDir));

            // Read FFmpeg output asynchronously and wait for process exit
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
                        // Rename and save whenever the file has content, regardless of exit code
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
     * Rename temp file to final filename based on actual recording duration.
     */
    private void renameToFinal(File tempFile, File outputDir, LocalDateTime startTime) {
        long durationMs = java.time.Duration.between(startTime, LocalDateTime.now()).toMillis();
        long durationSec = Math.max(1, durationMs / 1000); // at least 1 second
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
     * Stop recording for the specified camera.
     */
    public void stopRecording(Integer cameraId) {
        RecordingTask task = activeRecordings.remove(cameraId);
        if (task == null) return;

        // Stop the process if still running
        if (task.process.isAlive()) {
            task.process.destroy(); // send SIGTERM; FFmpeg saves recorded portion
            // Wait for process exit so FFmpeg flushes buffers to disk
            try {
                task.process.waitFor(5, java.util.concurrent.TimeUnit.SECONDS);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
        }

        // Rename temp file if it exists, whether or not the process is still running
        if (task.tempFile.exists() && task.tempFile.length() > 0) {
            renameToFinal(task.tempFile, task.outputDir, task.startTime);
        }
        log.info("Stopped recording for camera {}", cameraId);
    }

    /**
     * Stop all recordings (wait for processes to finish so files are fully written).
     */
    public void stopAllRecordings() {
        // Stop all running processes first
        activeRecordings.forEach((cameraId, task) -> {
            if (task.process.isAlive()) {
                task.process.destroy();
            }
        });
        // Wait for all processes to finish so FFmpeg flushes buffers to disk
        activeRecordings.forEach((cameraId, task) -> {
            try {
                task.process.waitFor(5, java.util.concurrent.TimeUnit.SECONDS);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
        });
        // Rename all temp files
        activeRecordings.forEach((cameraId, task) -> {
            if (task.tempFile.exists() && task.tempFile.length() > 0) {
                renameToFinal(task.tempFile, task.outputDir, task.startTime);
            }
        });
        activeRecordings.clear();
        log.info("Stopped all recordings");
    }

    /**
     * List recording files for a camera on a given date (excludes in-progress temp files).
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
     * Get a specific recording file for a camera, date, and filename.
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
     * Delete a specific recording file.
     * @return true if deleted, false if file does not exist
     */
    public boolean deleteRecording(Integer cameraId, String date, String fileName) {
        File file = getRecordingFile(cameraId, date, fileName);
        if (file == null) {
            return false;
        }
        return file.delete();
    }
}
