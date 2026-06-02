package com.hamster.yingshi.controller;

import com.hamster.yingshi.common.Result;
import com.hamster.yingshi.service.EzvizService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/templates")
public class TemplateController {

    @Autowired
    private EzvizService ezvizService;

    @GetMapping
    public Result<List<Map<String, Object>>> getTemplates() {
        List<Map<String, Object>> templates = ezvizService.getTemplateList();
        return Result.success(templates);
    }

    @PutMapping("/{templateId}/segment-duration")
    public Result<Void> updateSegmentDuration(
            @PathVariable Long templateId,
            @RequestParam(defaultValue = "300") int segmentDuration) {
        // 先查模板列表拿到模板信息
        List<Map<String, Object>> templates = ezvizService.getTemplateList();
        Map<String, Object> target = null;
        for (Map<String, Object> t : templates) {
            if (templateId.equals(((Number) t.get("templateId")).longValue())) {
                target = t;
                break;
            }
        }
        if (target == null) {
            return Result.error(404, "模板不存在: " + templateId);
        }
        ezvizService.updateTemplate(
                templateId,
                (String) target.get("templateName"),
                (String) target.get("format"),
                ((Number) target.get("spaceId")).longValue(),
                segmentDuration,
                (String) target.get("audioFormat")
        );
        return Result.success(null);
    }
}
