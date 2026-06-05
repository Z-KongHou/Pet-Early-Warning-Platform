package com.hamster.yingshi.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("activity_history")
public class ActivityHistory {
    @TableId(value = "id", type = IdType.AUTO)
    private Integer id;

    private Integer userId;

    private Integer hamsterId;

    private Integer cameraId;

    private Integer activityScore;

    private String status;

    private String analysisResult;

    private String imageUrl;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}