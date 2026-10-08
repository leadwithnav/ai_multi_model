def send_notification(channel, recipient, message, urgent=False):
    if channel == "email":
        if not recipient:
            raise ValueError("recipient required")

        subject = "URGENT" if urgent else "Notification"
        body = message.strip()

        return {
            "provider": "email",
            "recipient": recipient.lower(),
            "subject": subject,
            "body": body,
        }

    elif channel == "sms":
        if not recipient:
            raise ValueError("recipient required")

        body = message.strip()

        if urgent:
            body = "[URGENT] " + body

        return {
            "provider": "sms",
            "recipient": recipient,
            "body": body[:160],
        }

    elif channel == "push":
        if not recipient:
            raise ValueError("recipient required")

        body = message.strip()

        return {
            "provider": "push",
            "recipient": recipient,
            "title": "Urgent" if urgent else "Notification",
            "body": body,
            "priority": "high" if urgent else "normal",
        }

    else:
        raise ValueError("unsupported channel")