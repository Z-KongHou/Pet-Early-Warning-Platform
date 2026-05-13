package com.hamster.yingshi.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.hamster.yingshi.entity.User;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface UserMapper extends BaseMapper<User> {
}