package com.hamster.yingshi.controller;

import com.hamster.yingshi.common.ErrorCode;
import com.hamster.yingshi.common.Result;
import com.hamster.yingshi.dto.CameraRequest;
import com.hamster.yingshi.dto.CameraTokenRequest;
import com.hamster.yingshi.entity.Camera;
import com.hamster.yingshi.service.CameraService;
import com.hamster.yingshi.service.EzvizService;
import com.hamster.yingshi.service.UserCameraService;
import com.hamster.yingshi.utils.SecurityUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URI;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/cameras")
public class CameraController {

    @Autowired
    private CameraService cameraService;

    @Autowired
    private UserCameraService userCameraService;

    @Autowired
    private SecurityUtils securityUtils;

    @Autowired
    private EzvizService ezvizService;

    @PostMapping
    public Result<Camera> create(@RequestBody CameraRequest request) {
        Integer userId = securityUtils.getCurrentUserId();
        Camera camera = new Camera();
        camera.setHamsterId(request.getHamsterId());
        camera.setName(request.getName());
        camera.setDeviceKey(request.getDeviceKey());
        camera.setChannelNo(request.getChannelNo() != null ? request.getChannelNo() : 1);
        camera.setOnlineStatus(0);
        camera.setIsDeleted(0);
        Camera created = cameraService.create(camera);
        userCameraService.bind(userId, created.getId());
        return Result.success(created);
    }

    @GetMapping
    public Result<Map<String, Object>> list(@RequestParam(required = false) Integer hamsterId) {
        Integer userId = securityUtils.getCurrentUserId();
        List<Camera> cameras;
        if (hamsterId != null) {
            cameras = cameraService.findByHamsterId(hamsterId);
            cameras = cameras.stream()
                .filter(c -> cameraService.hasAccess(userId, c.getId()))
                .collect(Collectors.toList());
        } else {
            cameras = cameraService.findByUserId(userId);
        }
        List<Map<String, Object>> list = cameras.stream().map(c -> {
            Map<String, Object> item = new java.util.HashMap<>();
            item.put("id", c.getId());
            item.put("hamsterId", c.getHamsterId());
            item.put("name", c.getName());
            item.put("deviceKey", c.getDeviceKey());
            item.put("onlineStatus", c.getOnlineStatus());
            item.put("lastOnlineTime", c.getLastOnlineTime());
            return item;
        }).collect(Collectors.toList());
        Map<String, Object> data = new java.util.HashMap<>();
        data.put("list", list);
        data.put("total", list.size());
        return Result.success(data);
    }

    @GetMapping("/{id}")
    public Result<Camera> getById(@PathVariable Integer id) {
        Integer userId = securityUtils.getCurrentUserId();
        cameraService.checkAccess(userId, id);
        return Result.success(cameraService.findById(id));
    }

    @PostMapping("/{id}")
    public Result<Camera> update(@PathVariable Integer id, @RequestBody CameraRequest request) {
        Camera camera = new Camera();
        camera.setName(request.getName());
        camera.setChannelNo(request.getChannelNo());
        camera.setHamsterId(request.getHamsterId());
        return Result.success(cameraService.update(id, camera));
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Integer id) {
        cameraService.delete(id);
        return Result.success();
    }

    @GetMapping("/{id}/stream")
    public Result<Map<String, String>> getStream(@PathVariable Integer id) {
        Integer userId = securityUtils.getCurrentUserId();
        cameraService.checkAccess(userId, id);
        Camera camera = cameraService.findById(id);
        String streamUrl = ezvizService.getLiveStreamUrlWithRetry(camera);
        Map<String, String> data = new java.util.HashMap<>();
        data.put("streamUrl", streamUrl);
        String protocol = "flv";
        if (streamUrl.contains(".m3u8")) protocol = "hls";
        else if (streamUrl.contains("rtmp://")) protocol = "rtmp";
        data.put("protocol", protocol);
        data.put("accessToken", camera.getAccessToken());
        data.put("deviceKey", camera.getDeviceKey());
        data.put("channelNo", String.valueOf(camera.getChannelNo() != null ? camera.getChannelNo() : 1));
        return Result.success(data);
    }

    @GetMapping("/{id}/stream/proxy/**")
    public ResponseEntity<byte[]> proxyStream(@PathVariable Integer id,
                                              HttpServletRequest request) {
        Integer userId = securityUtils.getCurrentUserId();
        cameraService.checkAccess(userId, id);
        Camera camera = cameraService.findById(id);

        // 从完整路径中提取 /** 部分，如 index.m3u8 或 12345.ts
        String fullPath = request.getRequestURI();
        String prefix = "/api/cameras/" + id + "/stream/proxy/";
        String suffix = fullPath.substring(fullPath.indexOf(prefix) + prefix.length());

        // 获取萤石直播地址
        String streamUrl;
        try {
            streamUrl = ezvizService.getLiveStreamUrlWithRetry(camera);
        } catch (com.hamster.yingshi.common.BusinessException e) {
            HttpStatus status = e.getCode().equals(ErrorCode.CAMERA_OFFLINE) ? HttpStatus.NOT_FOUND
                    : e.getCode().equals(ErrorCode.TOKEN_EXPIRED) ? HttpStatus.BAD_GATEWAY
                    : HttpStatus.BAD_GATEWAY;
            return ResponseEntity.status(status)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(("{\"code\":" + e.getCode() + ",\"message\":\"" + e.getMessage() + "\"}")
                            .getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }

        String basePath = streamUrl.substring(0, streamUrl.lastIndexOf('/') + 1);
        String targetUrl = basePath + suffix;
        if (request.getQueryString() != null) {
            targetUrl += "?" + request.getQueryString();
        }

        try {
            RestTemplate restTemplate = new RestTemplate();
            ResponseEntity<byte[]> remoteResponse = restTemplate.getForEntity(
                    URI.create(targetUrl), byte[].class);

            HttpHeaders headers = new HttpHeaders();
            // m3u8 需要改写其中的相对 URL 指向代理
            if (suffix.endsWith(".m3u8") || suffix.contains(".m3u8")) {
                headers.setContentType(MediaType.parseMediaType("application/vnd.apple.mpegurl"));
                String m3u8 = new String(remoteResponse.getBody(), java.nio.charset.StandardCharsets.UTF_8);
                // 将相对路径的 .ts 引用改写为代理路径
                m3u8 = m3u8.replaceAll("((?!https?://)[^\\s]+?\\.ts)", prefix + "$1");
                return ResponseEntity.ok()
                        .headers(headers)
                        .cacheControl(CacheControl.noCache())
                        .body(m3u8.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            } else {
                // .ts 视频分片直接透传
                headers.setContentType(MediaType.parseMediaType("video/mp2t"));
                headers.setContentLength(remoteResponse.getBody() != null ? remoteResponse.getBody().length : 0);
                return ResponseEntity.ok()
                        .headers(headers)
                        .cacheControl(CacheControl.maxAge(java.time.Duration.ofSeconds(10)))
                        .body(remoteResponse.getBody());
            }
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                    .body(("代理请求失败: " + e.getMessage()).getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }
    }

    @GetMapping("/{id}/stream/live")
    public void proxyLiveStream(@PathVariable Integer id,
                                javax.servlet.http.HttpServletResponse response) {
        Integer userId = securityUtils.getCurrentUserId();
        cameraService.checkAccess(userId, id);
        Camera camera = cameraService.findById(id);

        String streamUrl;
        try {
            streamUrl = ezvizService.getLiveStreamUrlWithRetry(camera);
        } catch (com.hamster.yingshi.common.BusinessException e) {
            response.setStatus(HttpServletResponse.SC_BAD_GATEWAY);
            return;
        }

        response.setContentType("video/x-flv");
        response.setHeader("Cache-Control", "no-cache");
        response.setHeader("Connection", "keep-alive");
        response.setHeader("Access-Control-Allow-Origin", "*");

        try {
            URI uri = URI.create(streamUrl);
            java.net.HttpURLConnection conn = (java.net.HttpURLConnection) uri.toURL().openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(60000);
            conn.setRequestProperty("User-Agent", "Mozilla/5.0");

            try (InputStream is = conn.getInputStream();
                 OutputStream os = response.getOutputStream()) {
                byte[] buffer = new byte[4096];
                int len;
                while ((len = is.read(buffer)) != -1) {
                    os.write(buffer, 0, len);
                    os.flush();
                }
            }
        } catch (Exception ignored) {
        }
    }

    @GetMapping("/{id}/snapshot")
    public Result<Map<String, String>> getSnapshot(@PathVariable Integer id) {
        Integer userId = securityUtils.getCurrentUserId();
        cameraService.checkAccess(userId, id);
        Map<String, String> data = new java.util.HashMap<>();
        data.put("imageUrl", "https://placeholder-snapshot-url");
        return Result.success(data);
    }

    @PostMapping("/{id}/token")
    public Result<Void> updateToken(@PathVariable Integer id, @RequestBody CameraTokenRequest request) {
        LocalDateTime tokenExpires = LocalDateTime.parse(request.getTokenExpires());
        cameraService.updateToken(id, request.getAccessToken(), tokenExpires);
        return Result.success();
    }

    @GetMapping("/{id}/token")
    public Result<Map<String, Object>> getToken(@PathVariable Integer id) {
        Camera camera = cameraService.findById(id);
        Map<String, Object> data = new java.util.HashMap<>();
        data.put("cameraId", camera.getId());
        data.put("tokenExpires", camera.getTokenExpires());
        return Result.success(data);
    }
}