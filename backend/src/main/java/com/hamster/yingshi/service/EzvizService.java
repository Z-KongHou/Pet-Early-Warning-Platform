package com.hamster.yingshi.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hamster.yingshi.common.BusinessException;
import com.hamster.yingshi.common.ErrorCode;
import com.hamster.yingshi.config.EzvizProperties;
import com.hamster.yingshi.dto.ezviz.EzvizTokenResponse;
import com.hamster.yingshi.dto.ezviz.EzvizLiveResponse;
import com.hamster.yingshi.dto.ezviz.EzvizCloudVideoListResponse;
import com.hamster.yingshi.entity.Camera;
import com.hamster.yingshi.mapper.CameraMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class EzvizService {

    private static final Logger log = LoggerFactory.getLogger(EzvizService.class);

    private static final String TOKEN_URL = "https://open.ys7.com/api/lapp/token/get";
    private static final String LIVE_URL = "https://open.ys7.com/api/lapp/v2/live/address/get";
    private static final String CLOUD_VIDEO_LIST_URL = "https://open.ys7.com/api/lapp/cloud/video/list";
    private static final String DEVICE_INFO_URL = "https://open.ys7.com/api/lapp/device/info";

    @Autowired
    private EzvizProperties ezvizProperties;

    @Autowired
    private CameraMapper cameraMapper;

    private final RestTemplate restTemplate = new RestTemplate();
    private final ObjectMapper objectMapper = new ObjectMapper();

    private volatile String platformToken;
    private volatile long platformTokenExpireTime;

    public String getLiveStreamUrlWithRetry(Camera camera) {
        try {
            return getLiveStreamUrl(camera);
        } catch (BusinessException e) {
            if (e.getCode().equals(ErrorCode.TOKEN_EXPIRED)) {
                synchronized (this) {
                    platformToken = null;
                    platformTokenExpireTime = 0;
                }
                camera.setAccessToken(null);
                camera.setTokenExpires(null);
                return getLiveStreamUrl(camera);
            }
            throw e;
        }
    }

    public String getLiveStreamUrl(Camera camera) {
        String accessToken = ensureAccessToken(camera);
        return fetchLiveUrl(accessToken, camera.getDeviceKey(), camera.getChannelNo());
    }

    public List<Map<String, String>> getCloudRecordings(Camera camera, String startTime, String endTime) {
        String accessToken = ensureAccessToken(camera);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);

        int ch = camera.getChannelNo() != null ? camera.getChannelNo() : 1;
        MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
        body.add("accessToken", accessToken);
        body.add("deviceSerial", camera.getDeviceKey());
        body.add("channelNo", String.valueOf(ch));
        body.add("startTime", startTime);
        body.add("endTime", endTime);

        HttpEntity<MultiValueMap<String, String>> request = new HttpEntity<>(body, headers);
        log.info("Ezviz cloud recording list request: deviceSerial={}, channelNo={}, startTime={}, endTime={}",
                camera.getDeviceKey(), ch, startTime, endTime);

        ResponseEntity<String> response = restTemplate.exchange(
                CLOUD_VIDEO_LIST_URL, HttpMethod.POST, request, String.class);
        log.info("Ezviz cloud recording list response: {}", response.getBody());

        try {
            EzvizCloudVideoListResponse resp = objectMapper.readValue(
                    response.getBody(), EzvizCloudVideoListResponse.class);

            if ("200".equals(resp.getCode()) && resp.getData() != null && resp.getData().getList() != null) {
                List<Map<String, String>> result = new ArrayList<>();
                for (EzvizCloudVideoListResponse.VideoClip clip : resp.getData().getList()) {
                    Map<String, String> item = new HashMap<>();
                    item.put("startTime", clip.getStartTime());
                    item.put("endTime", clip.getEndTime());
                    item.put("fileSize", clip.getFileSize() != null ? String.valueOf(clip.getFileSize()) : "0");
                    item.put("recType", clip.getRecType() != null ? String.valueOf(clip.getRecType()) : "0");
                    if (clip.getThumbnail() != null) {
                        item.put("thumbnail", clip.getThumbnail());
                    }
                    result.add(item);
                }
                log.info("Cloud recording list fetched, count={}", result.size());
                return result;
            }

            log.warn("Ezviz cloud recording list error: code={}, msg={}", resp.getCode(), resp.getMsg());
            if ("10001".equals(resp.getCode()) || "10004".equals(resp.getCode())) {
                throw new BusinessException(ErrorCode.TOKEN_EXPIRED, "萤石Token已过期，请重试");
            }
            throw new BusinessException(ErrorCode.EZVIZ_API_ERROR,
                    "获取云录像列表失败(code=" + resp.getCode() + "): " + resp.getMsg());
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            throw new BusinessException(ErrorCode.EZVIZ_API_ERROR,
                    "解析萤石云录像列表响应失败: " + e.getMessage());
        }
    }

    private String ensureAccessToken(Camera camera) {
        if (camera.getAccessToken() != null && camera.getTokenExpires() != null
                && camera.getTokenExpires().isAfter(LocalDateTime.now().plusMinutes(5))) {
            return camera.getAccessToken();
        }

        String platformTk = getPlatformToken();

        LocalDateTime newExpiry = LocalDateTime.ofInstant(
                java.time.Instant.ofEpochMilli(platformTokenExpireTime),
                ZoneId.systemDefault());
        camera.setAccessToken(platformTk);
        camera.setTokenExpires(newExpiry);
        cameraMapper.updateById(camera);

        return platformTk;
    }

    private synchronized String getPlatformToken() {
        if (platformToken != null
                && platformTokenExpireTime > System.currentTimeMillis() + 300_000) {
            return platformToken;
        }

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);

        MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
        body.add("appKey", ezvizProperties.getAppKey());
        body.add("appSecret", ezvizProperties.getAppSecret());

        HttpEntity<MultiValueMap<String, String>> request = new HttpEntity<>(body, headers);
        ResponseEntity<String> response = restTemplate.exchange(
                TOKEN_URL, HttpMethod.POST, request, String.class);

        try {
            EzvizTokenResponse tokenResp = objectMapper.readValue(
                    response.getBody(), EzvizTokenResponse.class);
            if (!"200".equals(tokenResp.getCode())) {
                throw new BusinessException(ErrorCode.EZVIZ_API_ERROR,
                        "获取萤石Token失败: " + tokenResp.getMsg());
            }
            platformToken = tokenResp.getData().getAccessToken();
            platformTokenExpireTime = tokenResp.getData().getExpireTime();
            return platformToken;
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            throw new BusinessException(ErrorCode.EZVIZ_API_ERROR,
                    "解析萤石Token响应失败: " + e.getMessage());
        }
    }

    /**
     * 查询设备在线状态
     * @return true=在线, false=离线
     */
    public boolean checkDeviceOnline(Camera camera) {
        try {
            String accessToken = ensureAccessToken(camera);

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);

            MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
            body.add("accessToken", accessToken);
            body.add("deviceSerial", camera.getDeviceKey());

            HttpEntity<MultiValueMap<String, String>> request = new HttpEntity<>(body, headers);
            ResponseEntity<String> response = restTemplate.exchange(
                    DEVICE_INFO_URL, HttpMethod.POST, request, String.class);

            // 解析响应
            com.fasterxml.jackson.databind.JsonNode root = objectMapper.readTree(response.getBody());
            String code = root.path("code").asText();

            if ("200".equals(code)) {
                com.fasterxml.jackson.databind.JsonNode data = root.path("data");
                if (data != null && !data.isNull()) {
                    int status = data.path("status").asInt(0);
                    // status: 1=在线, 2=离线
                    return status == 1;
                }
            }

            log.warn("Failed to query device online status: deviceKey={}, code={}, msg={}",
                    camera.getDeviceKey(), code, root.path("msg").asText());
            return false;
        } catch (Exception e) {
            log.error("Device online status query failed: deviceKey={}, error={}", camera.getDeviceKey(), e.getMessage());
            return false;
        }
    }

    private String fetchLiveUrl(String accessToken, String deviceSerial, Integer channelNo) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);

        int ch = channelNo != null ? channelNo : 1;
        MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
        body.add("accessToken", accessToken);
        body.add("deviceSerial", deviceSerial);
        body.add("channelNo", String.valueOf(ch));
        body.add("protocol", "4"); // 4=flv

        HttpEntity<MultiValueMap<String, String>> request = new HttpEntity<>(body, headers);
        log.info("Ezviz v2 live API request: deviceSerial={}, channelNo={}", deviceSerial, ch);
        ResponseEntity<String> response = restTemplate.exchange(
                LIVE_URL, HttpMethod.POST, request, String.class);

        log.info("Ezviz v2 live API response: {}", response.getBody());

        try {
            EzvizLiveResponse liveResp = objectMapper.readValue(
                    response.getBody(), EzvizLiveResponse.class);

            if ("200".equals(liveResp.getCode()) && liveResp.getData() != null) {
                String url = liveResp.getData().getUrl();
                if (url != null && !url.isEmpty()) {
                    log.info("Live stream URL fetched, expireTime={}", liveResp.getData().getExpireTime());
                    return url;
                }
                throw new BusinessException(ErrorCode.EZVIZ_API_ERROR, "萤石未返回有效的直播地址");
            }

            log.warn("Ezviz v2 live API error: code={}, msg={}", liveResp.getCode(), liveResp.getMsg());

            if ("10002".equals(liveResp.getCode())) {
                throw new BusinessException(ErrorCode.CAMERA_OFFLINE, "摄像头不在线");
            }
            if ("10001".equals(liveResp.getCode()) || "10004".equals(liveResp.getCode())) {
                throw new BusinessException(ErrorCode.TOKEN_EXPIRED, "萤石Token已过期，请重试");
            }

            throw new BusinessException(ErrorCode.EZVIZ_API_ERROR,
                    "获取直播地址失败(code=" + liveResp.getCode() + "): " + liveResp.getMsg());
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            throw new BusinessException(ErrorCode.EZVIZ_API_ERROR,
                    "解析萤石直播响应失败: " + e.getMessage());
        }
    }
}
