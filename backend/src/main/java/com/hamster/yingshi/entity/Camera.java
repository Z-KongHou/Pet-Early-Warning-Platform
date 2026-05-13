package com.hamster.yingshi.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("cameras")
public class Camera {
    @TableId(value = "id", type = IdType.AUTO)
    private Integer id;

    private Integer hamsterId;

    private String name;

    private String deviceKey;

    private Integer channelNo;

    private String accessToken;

    private LocalDateTime tokenExpires;

    private LocalDateTime lastOnlineTime;

    private Integer onlineStatus;

    @TableField(select = false)
    private Integer isDeleted;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableField(select = false)
    private LocalDateTime deletedAt;
}