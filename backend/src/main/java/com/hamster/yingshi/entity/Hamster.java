package com.hamster.yingshi.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
@TableName("hamsters")
public class Hamster {
    @TableId(value = "id", type = IdType.AUTO)
    private Integer id;

    private Integer userId;

    private String name;

    private String breed;

    private LocalDate birthDate;

    private Integer gender;

    private BigDecimal weight;

    private String avatar;

    private String remark;

    private Integer healthStatus;

    @TableField(select = false)
    private Integer isDeleted;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableField(select = false)
    private LocalDateTime deletedAt;
}