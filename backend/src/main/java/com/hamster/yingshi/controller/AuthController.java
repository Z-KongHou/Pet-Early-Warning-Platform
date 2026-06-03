package com.hamster.yingshi.controller;

import com.hamster.yingshi.common.Result;
import com.hamster.yingshi.common.ErrorCode;
import com.hamster.yingshi.common.BusinessException;
import com.hamster.yingshi.dto.LoginRequest;
import com.hamster.yingshi.entity.User;
import com.hamster.yingshi.service.UserService;
import com.hamster.yingshi.service.SettingService;
import com.hamster.yingshi.utils.JwtUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import javax.validation.Valid;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    @Autowired
    private UserService userService;

    @Autowired
    private SettingService settingService;

    @Autowired
    private JwtUtils jwtUtils;

    @PostMapping("/login")
    public Result<Map<String, Object>> login(@Valid @RequestBody LoginRequest request) {
        User user = userService.findByUsername(request.getUsername());
        if (user == null) {
            throw new BusinessException(ErrorCode.UNAUTHORIZED, "Invalid username or password");
        }
        if (!userService.validatePassword(user, request.getPassword())) {
            throw new BusinessException(ErrorCode.UNAUTHORIZED, "Invalid username or password");
        }
        String token = jwtUtils.generateToken(user.getUserId(), user.getUsername());
        Map<String, Object> data = new HashMap<>();
        data.put("token", token);
        data.put("expiresIn", jwtUtils.getExpiration());
        return Result.success(data);
    }

    @PostMapping("/register")
    public Result<Map<String, Object>> register(@RequestBody Map<String, String> request) {
        String username = request.get("username");
        String password = request.get("password");
        String email = request.get("email");

        // 检查用户名是否已存在
        if (userService.findByUsername(username) != null) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "该账号已注册，请重试！");
        }

        // 检查邮箱是否已存在
        if (email != null && !email.isEmpty() && userService.findByEmail(email) != null) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "该邮箱已被注册！");
        }

        // 注册新用户
        User user = userService.register(username, password, email);

        // 为新用户初始化默认配置
        settingService.initDefaultSettings(user.getUserId());

        // 注册成功后自动登录
        String token = jwtUtils.generateToken(user.getUserId(), user.getUsername());
        Map<String, Object> data = new HashMap<>();
        data.put("token", token);
        data.put("expiresIn", jwtUtils.getExpiration());
        return Result.success(data);
    }

    @PostMapping("/logout")
    public Result<Void> logout() {
        return Result.success();
    }

    @GetMapping("/me")
    public Result<User> getCurrentUser() {
        User user = userService.findByUsername(
            org.springframework.security.core.context.SecurityContextHolder
                .getContext().getAuthentication().getName()
        );
        user.setPasswordHash(null);
        return Result.success(user);
    }
}