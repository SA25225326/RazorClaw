/**
 * PoiClaw 飞书机器人 - Node.js 版本
 *
 * 使用 @larksuiteoapi/node-sdk 的 WebSocket 长连接模式
 * 调用 Python Agent API 处理消息
 *
 * 使用方式：
 *   1. 先启动 Python API：uv run python api_server.py
 *   2. 再启动飞书机器人：node feishu-bot.js
 */

require('dotenv').config();
const Lark = require('@larksuiteoapi/node-sdk');

// 配置
const APP_ID = process.env.FEISHU_APP_ID;
const APP_SECRET = process.env.FEISHU_APP_SECRET;
const AGENT_API_URL = process.env.AGENT_API_URL || 'http://127.0.0.1:8080';

// 检查配置
if (!APP_ID || !APP_SECRET) {
  console.error('错误：请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET 环境变量');
  process.exit(1);
}

console.log('========================================');
console.log('  PoiClaw Feishu Bot (Node.js)');
console.log('========================================');
console.log(`App ID: ${APP_ID}`);
console.log(`App Secret: ${APP_SECRET.substring(0, 10)}...`);
console.log(`Agent API: ${AGENT_API_URL}`);
console.log('');

// 创建飞书客户端（用于发送消息）
const client = new Lark.Client({
  appId: APP_ID,
  appSecret: APP_SECRET,
  appType: Lark.AppType.SelfBuild,
  domain: Lark.Domain.Feishu,
});

// 创建事件分发器
const eventDispatcher = new Lark.EventDispatcher({
  encryptKey: '',
  verificationToken: '',
});

/**
 * 调用 Python Agent API
 */
async function callAgentAPI(message, sessionId) {
  const fetch = (await import('node-fetch')).default;

  try {
    const response = await fetch(`${AGENT_API_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: message,
        session_id: sessionId,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      console.error('Agent API Error:', error);
      return `抱歉，处理您的请求时出错：${response.status} ${response.statusText}`;
    }

    const data = await response.json();
    return data.response;
  } catch (error) {
    console.error('Agent API Error:', error);
    return `抱歉，无法连接到 Agent 服务。请确认 api_server.py 正在运行。`;
  }
}

/**
 * 发送消息给用户
 */
async function sendMessage(openId, content) {
  try {
    const response = await client.im.message.create({
      params: {
        receive_id_type: 'open_id',
      },
      data: {
        receive_id: openId,
        msg_type: 'text',
        content: JSON.stringify({ text: content }),
      },
    });

    if (response.code !== 0) {
      console.error('发送消息失败:', response.msg);
      return false;
    }
    return true;
  } catch (error) {
    console.error('发送消息异常:', error);
    return false;
  }
}

/**
 * 处理收到的消息
 */
async function handleMessage(event) {
  const message = event.message;
  const sender = event.sender;

  // 只处理文本消息
  if (message.message_type !== 'text') {
    console.log(`忽略非文本消息: type=${message.message_type}`);
    return;
  }

  // 解析消息内容
  let text = '';
  try {
    const content = JSON.parse(message.content);
    text = content.text || '';
  } catch (e) {
    console.log('无法解析消息内容');
    return;
  }

  // 获取用户 ID（作为 session_id）
  const openId = sender.sender_id.open_id;

  console.log(`收到消息: open_id=${openId}, text=${text.substring(0, 50)}...`);

  // 调用 Python Agent API
  console.log('正在调用 Python Agent API...');
  const response = await callAgentAPI(text, openId);

  // 回复消息
  const success = await sendMessage(openId, response);
  if (success) {
    console.log('消息回复成功');
  } else {
    console.log('消息回复失败');
  }
}

// 注册消息事件处理器
eventDispatcher.register({
  'im.message.receive_v1': async (data) => {
    console.log('');
    console.log('========================================');
    console.log('🎉 收到消息事件！');
    console.log('========================================');

    try {
      await handleMessage(data);
    } catch (error) {
      console.error('处理消息异常:', error);
    }
  },
});

// 创建 WebSocket 客户端
const wsClient = new Lark.WSClient({
  appId: APP_ID,
  appSecret: APP_SECRET,
  appType: Lark.AppType.SelfBuild,
  domain: Lark.Domain.Feishu,
});

console.log('正在连接飞书 WebSocket...');
console.log('');
console.log('>>> 请确保 Python API 已启动：uv run python api_server.py <<<');
console.log('>>> 然后在飞书中给机器人发送消息测试 <<<');
console.log('');

// 启动 WebSocket 连接
wsClient.start({
  eventDispatcher: eventDispatcher,
});

console.log('WebSocket 客户端已启动');
