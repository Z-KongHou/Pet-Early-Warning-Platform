package com.hamster.yingshi.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Data
@Component
@ConfigurationProperties(prefix = "ezviz")
public class EzvizProperties {
    private String appKey;
    private String appSecret;
}
