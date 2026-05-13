package com.hamster.yingshi.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("messages")
public class Message {
    @TableId(value = "id", type = IdType.AUTO)
    private Integer id;

    private Integer hamsterId;

    private Integer alertId;

    private Integer userId;

    private String title;

    private String content;

    private Integer isRead;

    @TableField(select = false)
    private Integer isDeleted;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableField(select = false)
    private LocalDateTime deletedAt;
}