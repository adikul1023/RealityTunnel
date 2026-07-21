import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  try {
    const { transactionId, accountId, plan, price } = await request.json()
    
    const botToken = process.env.TELEGRAM_BOT_TOKEN
    const chatId = process.env.TELEGRAM_CHAT_ID

    if (!botToken || !chatId) {
      console.warn('Telegram bot token or chat ID not configured. Simulating success.')
      return NextResponse.json({ success: true, simulated: true })
    }

    const text =
      `💰 *New Payment Submitted*\n` +
      `━━━━━━━━━━━━━━━━━━━━\n` +
      `👤 *User ID:* \`${accountId}\`\n` +
      `📋 *Plan:* ${plan} — ${price}\n` +
      `🔖 *Transaction ID / UTR:*\n` +
      `\`${transactionId}\`\n` +
      `━━━━━━━━━━━━━━━━━━━━\n` +
      `_Verify in your bank app and approve the plan manually._`

    const telegramUrl = `https://api.telegram.org/bot${botToken}/sendMessage`
    
    const res = await fetch(telegramUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        chat_id: chatId,
        text,
        parse_mode: 'Markdown',
      }),
    })

    if (!res.ok) {
      throw new Error('Failed to send telegram message')
    }

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Error submitting transaction:', error)
    return NextResponse.json({ error: 'Failed to submit' }, { status: 500 })
  }
}
