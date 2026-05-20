package com.hamster.yingshi.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hamster.yingshi.common.BusinessException;
import com.hamster.yingshi.common.ErrorCode;
import com.hamster.yingshi.config.EzvizProperties;
import com.hamster.yingshi.dto.ezviz.EzvizTokenResponse;
import com.hamster.yingshi.dto.ezviz.EzvizLiveResponse;
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

@Service
public class EzvizService {

    private static final Logger log = LoggerFactory.getLogger(EzvizService.class);

    private static final String TOKEN_URL = "https://open.ys7.com/api/lapp/token/get";
    private static final String LIVE_URL = "https://open.ys7.com/api/lapp/v2/live/address/get";

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
        log.info("萤石v2直播API请求: deviceSerial={}, channelNo={}", deviceSerial, ch);
        ResponseEntity<String> response = restTemplate.exchange(
                LIVE_URL, HttpMethod.POST, request, String.class);

        log.info("萤石v2直播API响应: {}", response.getBody());

        try {
            EzvizLiveResponse liveResp = objectMapper.readValue(
                    response.getBody(), EzvizLiveResponse.class);

            if ("200".equals(liveResp.getCode()) && liveResp.getData() != null) {
                String url = liveResp.getData().getUrl();
                if (url != null && !url.isEmpty()) {
                    log.info("获取直播地址成功, expireTime={}", liveResp.getData().getExpireTime());
                    return url;
                }
                throw new BusinessException(ErrorCode.EZVIZ_API_ERROR, "萤石未返回有效的直播地址");
            }

            log.warn("萤石v2直播API错误: code={}, msg={}", liveResp.getCode(), liveResp.getMsg());

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
