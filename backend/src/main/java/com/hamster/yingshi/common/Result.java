package com.hamster.yingshi.common;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Data;
import java.util.UUID;

@Data
@JsonInclude(JsonInclude.Include.NON_NULL)
public class Result<T> {
    private Integer code;
    private String message;
    private T data;
    /** Matches frontend and gateway conventions; included only on error responses */
    private String requestId;

    public static <T> Result<T> success() {
        return success(null);
    }

    public static <T> Result<T> success(T data) {
        Result<T> result = new Result<>();
        result.setCode(200);
        result.setMessage("success");
        result.setData(data);
        return result;
    }

    public static <T> Result<T> error(Integer code, String message) {
        return error(code, message, UUID.randomUUID().toString());
    }

    public static <T> Result<T> error(Integer code, String message, String requestId) {
        Result<T> result = new Result<>();
        result.setCode(code);
        result.setMessage(message);
        result.setData(null);
        result.setRequestId(requestId);
        return result;
    }
}