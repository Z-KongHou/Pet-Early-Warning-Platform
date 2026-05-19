package com.hamster.yingshi.dto.ezviz;

import lombok.Data;

@Data
public class EzvizLiveResponse {
    private Integer code;
    private String msg;
    private LiveData data;

    @Data
    public static class LiveData {
        private String url;
        private String rtmpUrl;
        private String hdUrl;
    }
}
