package com.hamster.yingshi.controller;

import com.hamster.yingshi.common.BusinessException;
import com.hamster.yingshi.common.ErrorCode;
import com.hamster.yingshi.service.SseService;
import com.hamster.yingshi.utils.JwtUtils;
import com.hamster.yingshi.utils.SecurityUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/**
 * Real-time notification endpoint via Server-Sent Events.
 *
 * <p>Browser {@code EventSource} cannot set custom headers, so this endpoint
 * supports a {@code ?token=} query parameter as an alternative to the
 * {@code Authorization} header. The header is tried first; if missing or
 * invalid, the query param is used as fallback.</p>
 */
@RestController
@RequestMapping("/api/notifications")
public class NotificationController {

    @Autowired
    private SseService sseService;

    @Autowired
    private SecurityUtils securityUtils;

    @Autowired
    private JwtUtils jwtUtils;

    /**
     * Subscribe to real-time alert notifications.
     *
     * <pre>
     * // Frontend usage:
     * const es = new EventSource('/api/notifications/subscribe?token=' + jwt);
     * es.addEventListener('alert', e => { ... });
     * es.addEventListener('heartbeat', () => {});  // keep-alive
     * </pre>
     */
    @GetMapping(value = "/subscribe", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter subscribe(@RequestParam(required = false) String token) {
        Integer userId = null;

        // Try header-based auth first (works for curl / fetch with custom headers)
        try {
            userId = securityUtils.getCurrentUserId();
        } catch (Exception ignored) {
            // Fall through to query-param auth
        }

        // Fallback: query-param token (required by browser EventSource)
        if (userId == null && token != null && !token.isBlank()) {
            try {
                if (jwtUtils.validateToken(token)) {
                    userId = jwtUtils.getUserIdFromToken(token);
                }
            } catch (Exception e) {
                throw new BusinessException(ErrorCode.UNAUTHORIZED, "Invalid token");
            }
        }

        if (userId == null) {
            throw new BusinessException(ErrorCode.UNAUTHORIZED, "Authentication required");
        }

        return sseService.subscribe(userId);
    }
}
