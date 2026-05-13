package com.hamster.yingshi.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.hamster.yingshi.entity.Hamster;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface HamsterMapper extends BaseMapper<Hamster> {
}