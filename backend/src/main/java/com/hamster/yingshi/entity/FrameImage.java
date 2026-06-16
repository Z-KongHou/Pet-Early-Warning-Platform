package com.hamster.yingshi.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("frame_images")
public class FrameImage {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    private Integer userId;

    private String cameraId;

    private String requestId;

    private String originalFilename;

    private String filePath;

    private Integer fileSize;

    private LocalDateTime imageTimestamp;

    private String source;

    private String status;

    private LocalDateTime lastAccessedAt;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    private Integer hasPet;

    private Integer positionX;

    private Integer positionY;

    private Integer positionWidth;

    private Integer positionHeight;

    private Double confidence;

    private String foodStatus;

    private LocalDateTime analyzedAt;
}
