# Webhook notifications

In **Overview → Notifications**, paste a webhook URL, choose events and save it.
**Send test notification** saves a newly pasted URL first and sends a test message.
The platform is detected from the hostname. Leaving the URL blank when changing
event settings retains the saved secret. **Remove webhook** clears it.

| Platform | URL | Message layout |
|---|---|---|
| Discord | Channel incoming webhook URL | Cyan/sunset embed, status fields and timestamp; mentions disabled |
| Telegram | `https://api.telegram.org/botTOKEN/sendMessage?chat_id=CHAT_ID` | HTML heading and escaped fields; optional `message_thread_id` in the URL |
| Slack | Slack incoming webhook URL | Header and plain-text Block Kit fields |
| Generic | Other HTTP(S) JSON receiver | `source`, `event`, `title`, `text`, `fields`, `summary`, `timestamp` |

Telegram needs a bot token and destination chat ID; a token alone cannot identify
the recipient. Remote endpoints require HTTPS. HTTP is allowed for loopback
receivers used in local verification. Redirects are not followed.

Choose workflow completion/stoppage and optionally individual tool outcomes.
Workflow events are selected by default to avoid one message per tool. Summaries
include engagement, status, stage/tool counts and duration where relevant. Tool
notifications include the target origin, without URL paths, queries, session
credentials or raw scan output. Completed-limited workflows explicitly describe
their coverage limits. A successful process is not advertised as a vulnerability.

URLs and bot tokens are stored in an ignored private `secrets/notifications.json`
file with mode 0600. API responses contain only platform, hostname, enabled events
and delivery status. They do not return the saved URL or token. Settings are local
and are not committed. Queue delivery is bounded, best effort, and separate from
the scan worker. There are no automatic retries or delivery guarantees across a
restart. Changing/removing settings drops queued messages for the earlier config.

Payload references: [Discord webhooks](https://docs.discord.com/developers/resources/webhook),
[Telegram sendMessage](https://core.telegram.org/bots/api#sendmessage), and
[Slack incoming webhooks](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/).
