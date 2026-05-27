package com.hamster.yingshi.controller;

import com.hamster.yingshi.common.Result;
import com.hamster.yingshi.common.ErrorCode;
import com.hamster.yingshi.common.BusinessException;
import com.hamster.yingshi.dto.LoginRequest;
import com.hamster.yingshi.entity.User;
import com.hamster.yingshi.service.UserService;
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
        String token = jwtUtils.generateToken(user.getId(), user.getUsername());
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