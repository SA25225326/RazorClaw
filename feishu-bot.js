/**
 * PoiClaw 飞书机器人 - Node.js 版本
 *
 * 使用 @larksuiteoapi/node-sdk 的 WebSocket 长连接模式
 *
 * 使用方式：
 *   1. 安装依赖：npm install
 *   2. 配置 .env 文件
 *   3. 运行：node feishu-bot.js
 */

require('dotenv').config();
const Lark = require('@larksuiteoapi/node-sdk');

// 配置
const APP_ID = process.env.FEISHU_APP_ID;
const APP_SECRET = process.env.FEISHU_APP_SECRET;
const LLM_BASE_URL = process.env.OPENAI_BASE_URL;
const LLM_API_KEY = process.env.OPENAI_API_KEY;
const LLM_MODEL = process.env.OPENAI_MODEL || 'glm-4-flash';

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
console.log('');

// 创建飞书客户端（用于发送消息）- 完全按照 OpenClaw 的方式
const client = new Lark.Client({
  appId: APP_ID,
  appSecret: APP_SECRET,
  appType: Lark.AppType.SelfBuild,
  domain: Lark.Domain.Feishu,
});

// 创建事件分发器 - 完全按照 OpenClaw 的方式
const eventDispatcher = new Lark.EventDispatcher({
  encryptKey: '',
  verificationToken: '',
});

// 用户会话存储（简单的内存存储，生产环境应该用文件或数据库）
const userSessions = new Map();

/**
 * 调用 LLM API
 */
async function callLLM(userInput, messages) {
  const fetch = (await import('node-fetch')).default;

  // 构建消息历史
  const allMessages = [
    { role: 'system', content: '你是一个有帮助的 AI 助手。' },
    ...messages,
    { role: 'user', content: userInput }
  ];

  try {
    const response = await fetch(`${LLM_BASE_URL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${LLM_API_KEY}`,
      },
      body: JSON.stringify({
        model: LLM_MODEL,
        messages: allMessages,
        max_tokens: 2000,
      }),
    });

    const data = await response.json();

    if (data.error) {
      console.error('LLM API Error:', data.error);
      return `抱歉，调用 AI 时出错：${data.error.message}`;
    }

    return data.choices[0].message.content;
  } catch (error) {
    console.error('LLM Error:', error);
    return `抱歉，处理您的请求时出错：${error.message}`;
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

  // 获取用户 ID
  const openId = sender.sender_id.open_id;

  console.log(`收到消息: open_id=${openId}, text=${text.substring(0, 50)}...`);

  // 获取或创建用户会话
  if (!userSessions.has(openId)) {
    userSessions.set(openId, { messages: [] });
  }
  const session = userSessions.get(openId);

  // 调用 LLM
  console.log('正在调用 LLM...');
  const response = await callLLM(text, session.messages);

  // 保存对话历史
  session.messages.push({ role: 'user', content: text });
  session.messages.push({ role: 'assistant', content: response });

  // 限制历史长度（保留最近 20 条）
  if (session.messages.length > 20) {
    session.messages = session.messages.slice(-20);
  }

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
console.log('>>> 请在飞书中给机器人发送消息测试 <<<');
console.log('');

// 启动 WebSocket 连接
wsClient.start({
  eventDispatcher: eventDispatcher,
});

console.log('WebSocket 客户端已启动');
