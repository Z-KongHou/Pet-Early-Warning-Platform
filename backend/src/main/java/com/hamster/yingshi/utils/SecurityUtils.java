package com.hamster.yingshi.utils;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import com.hamster.yingshi.entity.User;
import com.hamster.yingshi.mapper.UserMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;

@Component
public class SecurityUtils {

    @Autowired
    private UserMapper userMapper;

    public Integer getCurrentUserId() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication != null && authentication.getPrincipal() instanceof UserDetailsImpl) {
            UserDetailsImpl userDetails = (UserDetailsImpl) authentication.getPrincipal();
            return userDetails.getUserId();
        }
        return null;
    }

    public String getCurrentUsername() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication != null && authentication.getPrincipal() instanceof UserDetailsImpl) {
            UserDetailsImpl userDetails = (UserDetailsImpl) authentication.getPrincipal();
            return userDetails.getUsername();
        }
        return null;
    }

    public User getCurrentUser() {
        Integer userId = getCurrentUserId();
        if (userId != null) {
            return userMapper.selectOne(new LambdaQueryWrapper<User>().eq(User::getUserId, userId));
        }
        return null;
    }
}