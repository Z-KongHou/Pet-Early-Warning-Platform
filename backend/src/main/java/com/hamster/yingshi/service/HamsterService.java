package com.hamster.yingshi.service;

import com.hamster.yingshi.entity.Hamster;
import com.hamster.yingshi.mapper.HamsterMapper;
import com.hamster.yingshi.common.BusinessException;
import com.hamster.yingshi.common.ErrorCode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import java.util.List;

@Service
public class HamsterService {

    @Autowired
    private HamsterMapper hamsterMapper;

    public Hamster create(Hamster hamster) {
        hamsterMapper.insert(hamster);
        return hamster;
    }

    public Hamster findById(Integer id) {
        Hamster hamster = hamsterMapper.selectOne(
            new LambdaQueryWrapper<Hamster>()
                .eq(Hamster::getId, id)
                .eq(Hamster::getIsDeleted, 0)
        );
        if (hamster == null) {
            throw new BusinessException(ErrorCode.HAMSTER_NOT_FOUND, "Hamster not found");
        }
        return hamster;
    }

    public List<Hamster> findAll() {
        return hamsterMapper.selectList(
            new LambdaQueryWrapper<Hamster>()
                .eq(Hamster::getIsDeleted, 0)
                .orderByDesc(Hamster::getCreatedAt)
        );
    }

    public List<Hamster> findByUserId(Integer userId) {
        return hamsterMapper.selectList(
            new LambdaQueryWrapper<Hamster>()
                .eq(Hamster::getUserId, userId)
                .eq(Hamster::getIsDeleted, 0)
                .orderByDesc(Hamster::getCreatedAt)
        );
    }

    public Page<Hamster> findPage(Integer page, Integer size) {
        Page<Hamster> pageParam = new Page<>(page, size);
        return hamsterMapper.selectPage(pageParam,
            new LambdaQueryWrapper<Hamster>()
                .eq(Hamster::getIsDeleted, 0)
                .orderByDesc(Hamster::getCreatedAt)
        );
    }

    public Hamster update(Integer id, Hamster hamster) {
        Hamster existing = findById(id);
        if (hamster.getName() != null) existing.setName(hamster.getName());
        if (hamster.getBreed() != null) existing.setBreed(hamster.getBreed());
        if (hamster.getBirthDate() != null) existing.setBirthDate(hamster.getBirthDate());
        if (hamster.getGender() != null) existing.setGender(hamster.getGender());
        if (hamster.getWeight() != null) existing.setWeight(hamster.getWeight());
        if (hamster.getAvatar() != null) existing.setAvatar(hamster.getAvatar());
        if (hamster.getRemark() != null) existing.setRemark(hamster.getRemark());
        if (hamster.getHealthStatus() != null) existing.setHealthStatus(hamster.getHealthStatus());
        hamsterMapper.updateById(existing);
        return existing;
    }

    public void delete(Integer id) {
        Hamster hamster = findById(id);
        hamsterMapper.update(null,
            new LambdaUpdateWrapper<Hamster>()
                .eq(Hamster::getId, id)
                .set(Hamster::getIsDeleted, 1)
        );
    }
}