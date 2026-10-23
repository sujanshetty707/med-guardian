import logging
from typing import Optional, Dict, Any
from tools.notify.telegram import telegram_notifier

logger = logging.getLogger("med-guardian.tools.notify.dispatcher")

class NotificationDispatcher:
    async def dispatch_reminder(
        self,
        patient_name: str,
        medication_name: str,
        strength: str,
        channel: str = "telegram",
        channel_addr: Optional[str] = None
    ) -> bool:
        msg = (
            f"🔔 **Medication Reminder for {patient_name}**\n\n"
            f"Time to take: **{medication_name}** ({strength})\n"
            f"Please reply 'Taken' or 'Skip'."
        )
        logger.info(f"Dispatching dose reminder via {channel}: {msg}")
        if channel == "telegram" and channel_addr:
            return await telegram_notifier.send_message(channel_addr, msg)
        return True

    async def dispatch_caregiver_alert(
        self,
        caregiver_name: str,
        patient_name: str,
        medication_name: str,
        strength: str,
        due_time: str,
        channel: str = "telegram",
        channel_addr: Optional[str] = None
    ) -> bool:
        msg = (
            f"⚠️ **Caregiver Alert: Missed Dose Detected**\n\n"
            f"Hello {caregiver_name},\n"
            f"{patient_name} has not confirmed their scheduled dose of **{medication_name} ({strength})** due at {due_time}.\n\n"
            f"Suggested actions:\n"
            f"• Call {patient_name} to check in\n"
            f"• Reply 'Snooze' for 30 minutes\n"
            f"• Reply 'Mark taken' if already verified"
        )
        logger.warning(f"[CAREGIVER ESCALATION] {msg}")
        if channel == "telegram" and channel_addr:
            return await telegram_notifier.send_message(channel_addr, msg)
        return True

dispatcher = NotificationDispatcher()
