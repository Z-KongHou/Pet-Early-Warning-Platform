package com.hamster.yingshi.controller;

import com.hamster.yingshi.common.Result;
import com.hamster.yingshi.dto.AnalysisRequest;
import com.hamster.yingshi.service.AnalysisService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/analysis")
public class AnalysisController {

    @Autowired
    private AnalysisService analysisService;

    @PostMapping("/activity")
    public Result<AnalysisService.AnalysisResult> analyzeActivity(
            @RequestBody AnalysisRequest request,
            @RequestParam(defaultValue = "false") boolean demo) {
        AnalysisService.AnalysisResult result = analysisService.analyzeActivity(
                request.getCameraId(), request.getImageUrl(), demo);
        return Result.success(result);
    }
}