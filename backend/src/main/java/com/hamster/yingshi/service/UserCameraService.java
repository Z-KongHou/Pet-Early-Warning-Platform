package com.hamster.yingshi.service;

import com.hamster.yingshi.entity.UserCamera;
import com.hamster.yingshi.mapper.UserCameraMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import java.time.LocalDateTime;
import java.util.List;

@Service
public class UserCameraService {

    @Autowired
    private UserCameraMapper userCameraMapper;

    @Transactional
    public UserCamera bind(Integer userId, Integer cameraId) {
        UserCamera existing = userCameraMapper.selectOne(
            new LambdaQueryWrapper<UserCamera>()
                .eq(UserCamera::getUserId, userId)
                .eq(UserCamera::getCameraId, cameraId)
        );
        if (existing != null) {
            if (existing.getIsDeleted() == 0) {
                return existing;
            }
            userCameraMapper.update(null,
                new LambdaUpdateWrapper<UserCamera>()
                    .eq(UserCamera::getId, existing.getId())
                    .set(UserCamera::getIsDeleted, 0)
                    .set(UserCamera::getDeletedAt, null)
            );
            existing.setIsDeleted(0);
            return existing;
        }
        UserCamera userCamera = new UserCamera();
        userCamera.setUserId(userId);
        userCamera.setCameraId(cameraId);
        userCamera.setIsDeleted(0);
        userCameraMapper.insert(userCamera);
        return userCamera;
    }

    @Transactional
    public void unbind(Integer userId, Integer cameraId) {
        userCameraMapper.update(null,
            new LambdaUpdateWrapper<UserCamera>()
                .eq(UserCamera::getUserId, userId)
                .eq(UserCamera::getCameraId, cameraId)
                .eq(UserCamera::getIsDeleted, 0)
                .set(UserCamera::getIsDeleted, 1)
                .set(UserCamera::getDeletedAt, LocalDateTime.now())
        );
    }

    public List<UserCamera> findByUserId(Integer userId) {
        return userCameraMapper.selectList(
            new LambdaQueryWrapper<UserCamera>()
                .eq(UserCamera::getUserId, userId)
                .eq(UserCamera::getIsDeleted, 0)
        );
    }

    public boolean isBound(Integer userId, Integer cameraId) {
        return userCameraMapper.selectCount(
            new LambdaQueryWrapper<UserCamera>()
                .eq(UserCamera::getUserId, userId)
                .eq(UserCamera::getCameraId, cameraId)
                .eq(UserCamera::getIsDeleted, 0)
        ) > 0;
    }
}