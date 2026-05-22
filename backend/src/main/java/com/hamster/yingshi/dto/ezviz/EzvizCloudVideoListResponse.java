package com.hamster.yingshi.dto.ezviz;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

import java.util.List;

@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class EzvizCloudVideoListResponse {
    private String code;
    private String msg;
    private CloudVideoData data;

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class CloudVideoData {
        private List<VideoClip> list;
        private Integer total;
    }

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class VideoClip {
        private String startTime;
        private String endTime;
        private Long fileSize;
        private String thumbnail;
        private Integer recType;
    }
}
