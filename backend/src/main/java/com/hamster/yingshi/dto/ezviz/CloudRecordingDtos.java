package com.hamster.yingshi.dto.ezviz;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.util.List;

public class CloudRecordingDtos {

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class CloudMetaResponse {
        private String code;
        private String msg;
        private String moreInfo;
    }

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class CloudSpaceResponse {
        private Meta meta;
        private SpaceData data;

        @Data
        @JsonIgnoreProperties(ignoreUnknown = true)
        public static class Meta {
            private int code;
            private String message;
        }

        @Data
        @JsonIgnoreProperties(ignoreUnknown = true)
        public static class SpaceData {
            private Long spaceId;
            private Integer totalSize;
            private Integer totalTimePlan;
            private Integer totalEventPlan;
            private String spaceName;
            private Integer storageType;
            private Integer expireDays;
            private Boolean primarySpace;
        }
    }

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class CloudPlanResponse {
        private Meta meta;
        private PlanData data;

        @Data
        @JsonIgnoreProperties(ignoreUnknown = true)
        public static class Meta {
            private int code;
            private String message;
        }

        @Data
        @JsonIgnoreProperties(ignoreUnknown = true)
        public static class PlanData {
            private Long oneOffPlanId;
            private String planName;
            private Long spaceId;
            private String startTime;
            private String endTime;
            private Integer planStatus;
            private String errorCode;
            private String errorMsg;
            private Integer deviceNum;
            private String createTime;
            private String updateTime;
            private Integer planType;
            private Boolean specifiedEndTime;
            private List<DevInfo> validDevInfos;
            private List<DevInfo> invalidDevInfos;

            @Data
            @JsonIgnoreProperties(ignoreUnknown = true)
            public static class DevInfo {
                private String deviceSerial;
                private String localIndex;
            }
        }
    }

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class CloudTaskListResponse {
        private Meta meta;
        private TaskData data;

        @Data
        @JsonIgnoreProperties(ignoreUnknown = true)
        public static class Meta {
            private int code;
            private String message;
        }

        @Data
        @JsonIgnoreProperties(ignoreUnknown = true)
        public static class TaskData {
            private List<TaskInfo> result;
            private Integer pageStart;
            private Integer pageSize;
            private Integer total;

            @Data
            @JsonIgnoreProperties(ignoreUnknown = true)
            public static class TaskInfo {
                private Long id;
                private Long planId;
                private Integer planType;
                private String startTime;
                private String endTime;
                private Integer taskType;
                private String taskDetail;
                private Long spaceId;
                private String deviceSerial;
                private String localIndex;
                private Long cloudTaskId;
                private Integer taskStatus;
                private String errorCode;
                private String errorMsg;
                private Long totalSize;
                private Long totalDuration;
                private Boolean haveVideos;
                private String createTime;
                private String updateTime;
            }
        }
    }

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class CloudCalendarResponse {
        private Meta meta;
        private List<String> data;

        @Data
        @JsonIgnoreProperties(ignoreUnknown = true)
        public static class Meta {
            private int code;
            private String message;
        }
    }

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class CloudVideoInfoResponse {
        private Meta meta;
        private List<VideoInfo> data;

        @Data
        @JsonIgnoreProperties(ignoreUnknown = true)
        public static class Meta {
            private int code;
            private String message;
        }

        @Data
        @JsonIgnoreProperties(ignoreUnknown = true)
        public static class VideoInfo {
            private Long id;
            private String fileId;
            private Long spaceId;
            private String deviceSerial;
            private String channelNo;
            private String ownerId;
            private Integer fileType;
            private Integer cloudType;
            private String fileIndex;
            private String startTime;
            private String stopTime;
            private Long fileSize;
            private Integer locked;
            private String createTime;
            private Integer crypt;
            private Long videoLong;
            private Integer type;
            private Integer videoType;
            private Integer totalDays;
            private Integer istorageVersion;
            private String downloadPath;
            private String coverPic;
        }
    }

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class CloudPlayAddressResponse {
        private String code;
        private String msg;
        private PlayData data;

        @Data
        @JsonIgnoreProperties(ignoreUnknown = true)
        public static class PlayData {
            private String id;
            private String url;
            private String expireTime;
        }
    }

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class CloudDeleteResponse {
        private Meta meta;
        private DeleteData data;

        @Data
        @JsonIgnoreProperties(ignoreUnknown = true)
        public static class Meta {
            private int code;
            private String message;
        }

        @Data
        @JsonIgnoreProperties(ignoreUnknown = true)
        public static class DeleteData {
            private List<Object> videos;
            private Boolean hasNext;
        }
    }

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class CloudStopResponse {
        private Meta meta;

        @Data
        @JsonIgnoreProperties(ignoreUnknown = true)
        public static class Meta {
            private int code;
            private String message;
        }
    }
}
