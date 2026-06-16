package com.hamster.yingshi.service;

import com.hamster.yingshi.entity.Message;
import com.hamster.yingshi.mapper.MessageMapper;
import com.hamster.yingshi.common.BusinessException;
import com.hamster.yingshi.common.ErrorCode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;

import java.util.List;

@Service
public class MessageService {

    @Autowired
    private MessageMapper messageMapper;

    @Autowired
    private AlertService alertService;

    public Message create(Message message) {
        messageMapper.insert(message);
        return message;
    }

    public Message findById(Integer id) {
        Message message = messageMapper.selectOne(
            new LambdaQueryWrapper<Message>()
                .eq(Message::getId, id)
                .eq(Message::getIsDeleted, 0)
        );
        if (message == null) {
            throw new BusinessException(ErrorCode.MESSAGE_NOT_FOUND, "Message not found");
        }
        return message;
    }

    public Page<Message> findPage(Integer page, Integer size, Integer userId, Integer isRead) {
        Page<Message> pageParam = new Page<>(page, size);
        LambdaQueryWrapper<Message> wrapper = new LambdaQueryWrapper<Message>()
            .eq(Message::getUserId, userId)
            .eq(Message::getIsDeleted, 0)
            .orderByDesc(Message::getCreatedAt);
        if (isRead != null) {
            wrapper.eq(Message::getIsRead, isRead);
        }
        return messageMapper.selectPage(pageParam, wrapper);
    }

    public Long getUnreadCount(Integer userId) {
        return messageMapper.selectCount(
            new LambdaQueryWrapper<Message>()
                .eq(Message::getUserId, userId)
                .eq(Message::getIsRead, 0)
                .eq(Message::getIsDeleted, 0)
        );
    }

    public void markAsRead(Integer id) {
        Message message = findById(id);
        message.setIsRead(1);
        messageMapper.updateById(message);

        // Cascade: mark the linked alert as handled (status=2)
        if (message.getAlertId() != null) {
            try {
                alertService.updateStatus(message.getAlertId(), 2, "用户已读站内信", null);
            } catch (Exception e) {
                // Alert may have been deleted — non-fatal
            }
        }
    }

    public void markAllAsRead(Integer userId) {
        // Fetch unread messages first to cascade alert updates
        List<Message> unreadMessages = messageMapper.selectList(
            new LambdaQueryWrapper<Message>()
                .eq(Message::getUserId, userId)
                .eq(Message::getIsRead, 0)
                .eq(Message::getIsDeleted, 0)
        );

        messageMapper.update(null,
            new LambdaUpdateWrapper<Message>()
                .eq(Message::getUserId, userId)
                .eq(Message::getIsRead, 0)
                .eq(Message::getIsDeleted, 0)
                .set(Message::getIsRead, 1)
        );

        // Cascade: mark all linked alerts as handled
        for (Message m : unreadMessages) {
            if (m.getAlertId() != null) {
                try {
                    alertService.updateStatus(m.getAlertId(), 2, "用户已读站内信（全部已读）", null);
                } catch (Exception e) {
                    // Alert may have been deleted — non-fatal
                }
            }
        }
    }

    public void delete(Integer id) {
        Message message = findById(id);
        messageMapper.update(null,
            new LambdaUpdateWrapper<Message>()
                .eq(Message::getId, id)
                .set(Message::getIsDeleted, 1)
        );
    }
}