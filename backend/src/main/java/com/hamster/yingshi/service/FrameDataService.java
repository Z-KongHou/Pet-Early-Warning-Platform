package com.hamster.yingshi.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.hamster.yingshi.entity.FrameImage;
import com.hamster.yingshi.entity.PetAnalysis;
import com.hamster.yingshi.entity.PetState;
import com.hamster.yingshi.mapper.FrameImageMapper;
import com.hamster.yingshi.mapper.PetAnalysisMapper;
import com.hamster.yingshi.mapper.PetStateMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Service
public class FrameDataService {

    @Autowired
    private FrameImageMapper frameImageMapper;

    @Autowired
    private PetStateMapper petStateMapper;

    @Autowired
    private PetAnalysisMapper petAnalysisMapper;

    private static final int MAX_FRAMES_PER_CAMERA = 500;
    private static final int MAX_PET_ANALYSIS_PER_USER = 20;

    // ==================== frame_images ====================

    public Long insertFrame(Integer userId, String cameraId, String requestId,
                            String originalFilename, String filePath, Integer fileSize,
                            LocalDateTime imageTimestamp, String source) {
        FrameImage frame = new FrameImage();
        frame.setUserId(userId);
        frame.setCameraId(cameraId);
        frame.setRequestId(requestId);
        frame.setOriginalFilename(originalFilename);
        frame.setFilePath(filePath);
        frame.setFileSize(fileSize);
        frame.setImageTimestamp(imageTimestamp);
        frame.setSource(source);
        frame.setStatus("stored");
        frame.setLastAccessedAt(LocalDateTime.now());
        frameImageMapper.insert(frame);
        return frame.getId();
    }

    public FrameImage getFrameById(Long id) {
        return frameImageMapper.selectById(id);
    }

    public List<FrameImage> getFramesInWindow(String cameraId, LocalDateTime latestTs, int windowSeconds) {
        LocalDateTime minTs = latestTs.minusSeconds(windowSeconds);
        return frameImageMapper.selectList(
            new LambdaQueryWrapper<FrameImage>()
                .eq(FrameImage::getCameraId, cameraId)
                .ge(FrameImage::getImageTimestamp, minTs)
                .le(FrameImage::getImageTimestamp, latestTs)
                .orderByAsc(FrameImage::getImageTimestamp)
        );
    }

    public FrameImage getLatestDetectedFrame(String cameraId, LocalDateTime beforeTs) {
        return frameImageMapper.selectOne(
            new LambdaQueryWrapper<FrameImage>()
                .eq(FrameImage::getCameraId, cameraId)
                .eq(FrameImage::getHasPet, 1)
                .isNotNull(FrameImage::getPositionX)
                .isNotNull(FrameImage::getAnalyzedAt)
                .lt(FrameImage::getImageTimestamp, beforeTs)
                .orderByDesc(FrameImage::getImageTimestamp)
                .last("LIMIT 1")
        );
    }

    public void updateFrameDetection(Long frameId, Integer hasPet,
                                      Integer posX, Integer posY, Integer posWidth, Integer posHeight,
                                      Double confidence, String foodStatus) {
        frameImageMapper.update(null,
            new LambdaUpdateWrapper<FrameImage>()
                .eq(FrameImage::getId, frameId)
                .set(FrameImage::getStatus, "analyzed")
                .set(FrameImage::getHasPet, hasPet)
                .set(FrameImage::getPositionX, posX)
                .set(FrameImage::getPositionY, posY)
                .set(FrameImage::getPositionWidth, posWidth)
                .set(FrameImage::getPositionHeight, posHeight)
                .set(FrameImage::getConfidence, confidence)
                .set(FrameImage::getFoodStatus, foodStatus)
                .set(FrameImage::getAnalyzedAt, LocalDateTime.now())
                .set(FrameImage::getLastAccessedAt, LocalDateTime.now())
        );
    }

    public void batchUpdateStatus(List<Long> frameIds, String status) {
        if (frameIds == null || frameIds.isEmpty()) return;
        frameImageMapper.update(null,
            new LambdaUpdateWrapper<FrameImage>()
                .in(FrameImage::getId, frameIds)
                .set(FrameImage::getStatus, status)
        );
    }

    public void batchTouchFrames(List<Long> frameIds) {
        if (frameIds == null || frameIds.isEmpty()) return;
        frameImageMapper.update(null,
            new LambdaUpdateWrapper<FrameImage>()
                .in(FrameImage::getId, frameIds)
                .set(FrameImage::getLastAccessedAt, LocalDateTime.now())
        );
    }

    public void evictLruFrames(String cameraId) {
        Long count = frameImageMapper.selectCount(
            new LambdaQueryWrapper<FrameImage>().eq(FrameImage::getCameraId, cameraId)
        );
        if (count <= MAX_FRAMES_PER_CAMERA) return;

        int excess = (int) (count - MAX_FRAMES_PER_CAMERA);
        List<FrameImage> toDelete = frameImageMapper.selectList(
            new LambdaQueryWrapper<FrameImage>()
                .eq(FrameImage::getCameraId, cameraId)
                .orderByAsc(FrameImage::getLastAccessedAt)
                .last("LIMIT " + excess)
        );
        for (FrameImage frame : toDelete) {
            frameImageMapper.deleteById(frame.getId());
        }
    }

    // ==================== pet_state ====================

    public PetState getOrCreatePetState(Integer userId, String cameraId) {
        PetState state = petStateMapper.selectOne(
            new LambdaQueryWrapper<PetState>().eq(PetState::getCameraId, cameraId)
        );
        if (state == null) {
            state = new PetState();
            state.setUserId(userId);
            state.setCameraId(cameraId);
            state.setStationaryStartTime(LocalDateTime.now());
            state.setTotalAnalyses(0);
            petStateMapper.insert(state);
        }
        return state;
    }

    public void updatePetState(String cameraId, Map<String, Object> updates) {
        PetState existing = petStateMapper.selectOne(
            new LambdaQueryWrapper<PetState>().eq(PetState::getCameraId, cameraId)
        );
        if (existing == null) return;

        LambdaUpdateWrapper<PetState> wrapper = new LambdaUpdateWrapper<PetState>()
            .eq(PetState::getCameraId, cameraId);

        if (updates.containsKey("last_position_x")) {
            wrapper.set(PetState::getLastPositionX, (Integer) updates.get("last_position_x"));
        }
        if (updates.containsKey("last_position_y")) {
            wrapper.set(PetState::getLastPositionY, (Integer) updates.get("last_position_y"));
        }
        if (updates.containsKey("last_position_width")) {
            wrapper.set(PetState::getLastPositionWidth, (Integer) updates.get("last_position_width"));
        }
        if (updates.containsKey("last_position_height")) {
            wrapper.set(PetState::getLastPositionHeight, (Integer) updates.get("last_position_height"));
        }
        if (updates.containsKey("last_eating_time")) {
            wrapper.set(PetState::getLastEatingTime, (LocalDateTime) updates.get("last_eating_time"));
        }
        if (updates.containsKey("stationary_start_time")) {
            wrapper.set(PetState::getStationaryStartTime, (LocalDateTime) updates.get("stationary_start_time"));
        }
        if (updates.containsKey("food_bowl_position_x")) {
            wrapper.set(PetState::getFoodBowlPositionX, (Integer) updates.get("food_bowl_position_x"));
        }
        if (updates.containsKey("food_bowl_position_y")) {
            wrapper.set(PetState::getFoodBowlPositionY, (Integer) updates.get("food_bowl_position_y"));
        }
        if (updates.containsKey("food_bowl_position_width")) {
            wrapper.set(PetState::getFoodBowlPositionWidth, (Integer) updates.get("food_bowl_position_width"));
        }
        if (updates.containsKey("food_bowl_position_height")) {
            wrapper.set(PetState::getFoodBowlPositionHeight, (Integer) updates.get("food_bowl_position_height"));
        }
        if (updates.containsKey("total_analyses")) {
            wrapper.set(PetState::getTotalAnalyses, (Integer) updates.get("total_analyses"));
        }

        petStateMapper.update(null, wrapper);
    }

    // ==================== pet_analysis ====================

    public List<PetAnalysis> getAnalysisHistory(String cameraId) {
        return petAnalysisMapper.selectList(
            new LambdaQueryWrapper<PetAnalysis>()
                .eq(PetAnalysis::getCameraId, cameraId)
                .orderByAsc(PetAnalysis::getTimestamp)
        );
    }

    /**
     * 每个用户只保留最新的 20 条 pet_analysis 记录，超出的按时间升序删除。
     */
    public void evictOldPetAnalysis(Integer userId) {
        Long count = petAnalysisMapper.selectCount(
            new LambdaQueryWrapper<PetAnalysis>().eq(PetAnalysis::getUserId, userId)
        );
        if (count <= MAX_PET_ANALYSIS_PER_USER) return;

        int excess = (int) (count - MAX_PET_ANALYSIS_PER_USER);
        List<PetAnalysis> toDelete = petAnalysisMapper.selectList(
            new LambdaQueryWrapper<PetAnalysis>()
                .eq(PetAnalysis::getUserId, userId)
                .orderByAsc(PetAnalysis::getTimestamp)
                .last("LIMIT " + excess)
        );
        for (PetAnalysis record : toDelete) {
            petAnalysisMapper.deleteById(record.getId());
        }
    }
}
