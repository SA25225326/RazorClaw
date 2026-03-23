/**
 * PM2 配置文件 - PoiClaw 飞书机器人
 *
 * 使用方式：
 *   pm2 start ecosystem.config.js     # 启动
 *   pm2 logs poiclaw-agent            # 查看日志
 *   pm2 stop poiclaw-agent            # 停止
 *   pm2 restart poiclaw-agent         # 重启
 *   pm2 delete poiclaw-agent          # 删除
 *   pm2 monit                         # 监控面板
 *
 * 注意：
 *   - 确保 .env 文件已配置好飞书和 LLM 凭证
 *   - Windows 使用 .venv/Scripts/python.exe
 *   - Linux/Mac 使用 .venv/bin/python
 */

module.exports = {
  apps: [
    {
      name: "poiclaw-agent",
      script: "main.py",

      // 解释器配置（Windows 路径）
      interpreter: ".venv/Scripts/python.exe",

      // 如果是 Linux/Mac，使用下面这行（注释掉上面的）
      // interpreter: ".venv/bin/python",

      // 进程配置
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: "500M",

      // 重启延迟（毫秒）
      // 防止 WebSocket 断线后无限极速重启（飞书限流）
      restart_delay: 3000,

      // 最小运行时间（毫秒）
      // 如果进程在 10 秒内退出，认为是异常启动，延迟重启
      min_uptime: "10s",

      // 最大重启次数
      // 1 分钟内最多重启 5 次
      max_restarts: 5,

      // 日志配置
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "logs/error.log",
      out_file: "logs/out.log",
      merge_logs: true,

      // 环境变量（可选，优先级低于 .env 文件）
      env: {
        NODE_ENV: "production",
        // 以下环境变量建议在 .env 文件中配置
        // FEISHU_APP_ID: "cli_xxx",
        // FEISHU_APP_SECRET: "xxx",
        // OPENAI_BASE_URL: "https://open.bigmodel.cn/api/paas/v4",
        // OPENAI_API_KEY: "xxx",
        // OPENAI_MODEL: "glm-5",
        // MAX_STEPS: "10",
        // SESSION_BASE_PATH: ".poiclaw",
      },

      // 开发环境配置（使用 pm2 start --env development）
      env_development: {
        NODE_ENV: "development",
      },
    },
  ],
};
