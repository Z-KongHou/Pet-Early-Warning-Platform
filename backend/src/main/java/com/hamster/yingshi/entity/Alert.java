package com.hamster.yingshi.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("alerts")
public class Alert {
    @TableId(value = "id", type = IdType.AUTO)
    private Integer id;

    private Integer hamsterId;

    private String activityStatus;

    private Integer activityScore;

    private Integer threshold;

    private String imageUrl;

    private Integer status;

    private Integer handlerId;

    private String handleRemark;

    @TableField(select = false)
    private Integer isDeleted;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    private LocalDateTime handledAt;

    @TableField(select = false)
    private LocalDateTime deletedAt;
}