package com.hamster.yingshi.dto.ezviz;

import lombok.Data;

@Data
public class EzvizTokenResponse {
    private Integer code;
    private String msg;
    private TokenData data;

    @Data
    public static class TokenData {
        private String accessToken;
        private Long expireTime;
    }
}
