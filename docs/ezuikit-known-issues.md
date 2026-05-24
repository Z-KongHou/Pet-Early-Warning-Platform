# EZUIKit 播放器已知问题（待处理）

> 记录时间：2026-05-24  
> 状态：暂缓，不影响当前基本播放功能

摄像头直播使用 `ezuikit-js@9.0.5`（`frontend/src/components/VideoPlayer.tsx`）时，浏览器控制台会持续出现以下两类日志。Next.js dev 会将 `[browser]` 前缀的日志转发到终端。

---

## 1. WASM 流式编译 MIME 类型警告

### 现象

```
wasm streaming compile failed: TypeError: Failed to execute 'compile' on 'WebAssembly':
Incorrect response MIME type. Expected 'application/wasm'.
falling back to ArrayBuffer instantiation
```

资源来源：`https://openstatic.ys7.com/ezuikit_js/v9.0.5/ezuikit_static/.../Decoder.js`

### 原因

萤石 CDN 返回 `.wasm` 文件时，`Content-Type` 不是 `application/wasm`，浏览器拒绝流式编译。SDK 会自动降级为 ArrayBuffer 加载，**一般不影响播放**，但会刷警告且初始化稍慢。

### 后续方案（官方推荐）

1. 将 `node_modules/ezuikit-js/ezuikit_static` 复制到 `frontend/public/ezuikit_static/`
2. 播放器初始化增加 `staticPath: "/ezuikit_static"`
3. 在 `next.config.ts` 为 `.wasm` 配置响应头：

   ```ts
   async headers() {
     return [
       {
         source: "/ezuikit_static/:path*.wasm",
         headers: [{ key: "Content-Type", value: "application/wasm" }],
       },
     ];
   }
   ```

4. 可选：postinstall 脚本自动复制静态资源（体积较大，不宜提交 git）

---

## 2. Broadcast 模块预申请麦克风权限

### 现象

```
[Broadcast] 麦克风权限获取失败，将在首次录音时再次请求
NotAllowedError: Permission dismissed / Permission denied
```

### 原因

EZUIKit 内置对讲/广播（Broadcast）能力，初始化时会预调用 `getUserMedia` 申请麦克风。  
即使已设置 `template: "simple"`，v9 仍可能预加载 Broadcast 模块并尝试申请权限。  
用户拒绝或关闭授权弹窗后，SDK 会记录失败并在日志中提示。

**不影响看视频**，只影响向摄像头说话（对讲/广播）。

### 已做

- `VideoPlayer.tsx` 已设置 `template: "simple"`（极简模板，无对讲 UI）

### 后续方案

1. 使用 `themeData` 自定义主题，明确排除 `talk` / `broadcast` 控件
2. 确保未配置 `plugin: ["talk"]`
3. 可选：`loggerOptions: { level: "ERROR" }` 减少 SDK 日志（无法完全消除 Broadcast 的 console 输出）
4. 若完全不需要对讲，无需在浏览器中授予麦克风权限

---

## 相关文件

| 文件 | 说明 |
|------|------|
| `frontend/src/components/VideoPlayer.tsx` | EZUIKit 播放器封装 |
| `frontend/next.config.ts` | Next.js 配置（待加 wasm headers） |
| `frontend/package.json` | 依赖 `ezuikit-js@^9.0.5` |
