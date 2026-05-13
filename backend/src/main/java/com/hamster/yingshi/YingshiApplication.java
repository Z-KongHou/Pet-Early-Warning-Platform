package com.hamster.yingshi;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("com.hamster.yingshi.mapper")
public class YingshiApplication {
    public static void main(String[] args) {
        SpringApplication.run(YingshiApplication.class, args);
    }
}