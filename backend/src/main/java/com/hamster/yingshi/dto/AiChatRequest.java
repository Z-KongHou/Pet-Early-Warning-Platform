package com.hamster.yingshi.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
public class AiChatRequest {
    private String model;
    private List<Message> messages;

    public AiChatRequest(String model, List<Message> messages) {
        this.model = model;
        this.messages = messages;
    }

    @Data
    @AllArgsConstructor
    @NoArgsConstructor
    public static class Message {
        private String role;
        private String content;
    }
}