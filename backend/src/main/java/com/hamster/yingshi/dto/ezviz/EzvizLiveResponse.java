package com.hamster.yingshi.dto.ezviz;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class EzvizLiveResponse {
    private String code;
    private String msg;
    private LiveData data;

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class LiveData {
        private String id;
        private String url;
        private String expireTime;
    }
}
