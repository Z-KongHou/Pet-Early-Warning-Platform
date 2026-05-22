package com.hamster.yingshi.service;

import com.hamster.yingshi.entity.Camera;
import com.hamster.yingshi.entity.UserCamera;
import com.hamster.yingshi.mapper.CameraMapper;
import com.hamster.yingshi.mapper.UserCameraMapper;
import com.hamster.yingshi.common.BusinessException;
import com.hamster.yingshi.common.ErrorCode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import java.time.LocalDateTime;
import java.util.List;

@Service
public class CameraService {

    @Autowired
    private CameraMapper cameraMapper;

    @Autowired
    private UserCameraMapper userCameraMapper;

    public Camera create(Camera camera) {
        cameraMapper.insert(camera);
        return camera;
    }

    public Camera findById(Integer id) {
        Camera camera = cameraMapper.selectOne(
            new LambdaQueryWrapper<Camera>()
                .eq(Camera::getId, id)
                .eq(Camera::getIsDeleted, 0)
        );
        if (camera == null) {
            throw new BusinessException(ErrorCode.CAMERA_NOT_FOUND, "摄像头不存在");
        }
        return camera;
    }

    public List<Camera> findByHamsterId(Integer hamsterId) {
        return cameraMapper.selectList(
            new LambdaQueryWrapper<Camera>()
                .eq(Camera::getHamsterId, hamsterId)
                .eq(Camera::getIsDeleted, 0)
                .orderByDesc(Camera::getCreatedAt)
        );
    }

    public Page<Camera> findPage(Integer page, Integer size, Integer hamsterId) {
        Page<Camera> pageParam = new Page<>(page, size);
        LambdaQueryWrapper<Camera> wrapper = new LambdaQueryWrapper<Camera>()
            .eq(Camera::getIsDeleted, 0)
            .orderByDesc(Camera::getCreatedAt);
        if (hamsterId != null) {
            wrapper.eq(Camera::getHamsterId, hamsterId);
        }
        return cameraMapper.selectPage(pageParam, wrapper);
    }

    public List<Camera> findByUserId(Integer userId) {
        List<UserCamera> userCameras = userCameraMapper.selectList(
            new LambdaQueryWrapper<UserCamera>()
                .eq(UserCamera::getUserId, userId)
                .eq(UserCamera::getIsDeleted, 0)
        );
        if (userCameras.isEmpty()) {
            return List.of();
        }
        List<Integer> cameraIds = userCameras.stream().map(UserCamera::getCameraId).collect(java.util.stream.Collectors.toList());
        return cameraMapper.selectList(
            new LambdaQueryWrapper<Camera>()
                .in(Camera::getId, cameraIds)
                .eq(Camera::getIsDeleted, 0)
        );
    }

    public Camera update(Integer id, Camera camera) {
        Camera existing = findById(id);
        if (camera.getName() != null) existing.setName(camera.getName());
        if (camera.getChannelNo() != null) existing.setChannelNo(camera.getChannelNo());
        if (camera.getHamsterId() != null) existing.setHamsterId(camera.getHamsterId());
        if (camera.getRecordingEnabled() != null) existing.setRecordingEnabled(camera.getRecordingEnabled());
        cameraMapper.updateById(existing);
        return existing;
    }

    @Transactional
    public void delete(Integer id) {
        cameraMapper.update(null,
            new LambdaUpdateWrapper<Camera>()
                .eq(Camera::getId, id)
                .set(Camera::getIsDeleted, 1)
                .set(Camera::getDeletedAt, LocalDateTime.now())
        );
    }

    public void updateToken(Integer id, String accessToken, LocalDateTime tokenExpires) {
        Camera camera = findById(id);
        camera.setAccessToken(accessToken);
        camera.setTokenExpires(tokenExpires);
        cameraMapper.updateById(camera);
    }

    public List<Camera> findAll() {
        return cameraMapper.selectList(
            new LambdaQueryWrapper<Camera>()
                .eq(Camera::getIsDeleted, 0)
        );
    }

    public boolean hasAccess(Integer userId, Integer cameraId) {
        return userCameraMapper.selectCount(
            new LambdaQueryWrapper<UserCamera>()
                .eq(UserCamera::getUserId, userId)
                .eq(UserCamera::getCameraId, cameraId)
                .eq(UserCamera::getIsDeleted, 0)
        ) > 0;
    }

    public void checkAccess(Integer userId, Integer cameraId) {
        if (!hasAccess(userId, cameraId)) {
            throw new BusinessException(ErrorCode.FORBIDDEN, "无权限访问该摄像头");
        }
    }
}