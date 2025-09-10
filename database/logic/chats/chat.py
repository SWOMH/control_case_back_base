from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime
from typing import Optional, List
from database.decorator import connection
from database.models.support import Chat, ChatMessage, ChatAttachment, \
    ChatParticipant, SupportHistoryChat, SupportHistoryDate, \
    MessageReadReceipt, ClientLawyerAssignment
from database.main_connection import DataBaseMainConnect


class ChatSupport(DataBaseMainConnect):

    @connection
    async def get_active_chat_by_user(self, user_id: int, session: AsyncSession) -> Optional[Chat]:
        q = select(Chat).where(Chat.user_id == user_id,
                               Chat.active == True)
        res = await session.execute(q)
        return res.scalars().first()

    @connection
    async def create_chat(self, session: AsyncSession, user_id: int, initial_support_id: Optional[int] = None) -> Chat:
        chat = Chat(user_id=user_id, user_support_id=initial_support_id)
        session.add(chat)
        await session.flush()
        part = ChatParticipant(chat_id=chat.id, user_id=user_id, role="client")
        session.add(part)
        await session.commit()
        await session.refresh(chat)
        return chat

    @connection
    async def add_message(self, session: AsyncSession, chat_id: int, sender_id: Optional[int], sender_type: str,
                          text: Optional[str]) -> ChatMessage:
        msg = ChatMessage(chat_id=chat_id, sender_id=sender_id, sender_type=sender_type, message=text)
        session.add(msg)
        await session.flush()
        await session.commit()
        await session.refresh(msg)
        return msg

    @connection
    async def add_attachment(self, session: AsyncSession, message_id: int, filename: str,
                             file_path: str, content_type: str, size: int) -> ChatAttachment:
        att = ChatAttachment(message_id=message_id, filename=filename, file_path=file_path, content_type=content_type,
                             size=size)
        session.add(att)
        await session.commit()
        await session.refresh(att)
        return att

    @connection
    async def mark_messages_read(self, session: AsyncSession, chat_id: int, reader_user_id: int,
                                 upto_message_id: Optional[int] = None):
        """
        Добавляет записи MessageReadReceipt для непрочитанных сообщений.
        Простая реализация: для всех сообщений в чате, где нет receipt от reader_user_id -> добавляем.
        """
        q = select(ChatMessage).where(ChatMessage.chat_id == chat_id)
        if upto_message_id:
            q = q.where(ChatMessage.id <= upto_message_id)
        res = await session.execute(q)
        messages = res.scalars().all()
        for m in messages:
            # проверяем, есть ли уже
            q2 = select(MessageReadReceipt).where(MessageReadReceipt.message_id == m.id,
                                                  MessageReadReceipt.user_id == reader_user_id)
            has = (await session.execute(q2)).scalars().first()
            if not has:
                receipt = MessageReadReceipt(message_id=m.id, user_id=reader_user_id, read_at=datetime.utcnow())
                session.add(receipt)
        await session.commit()

    @connection
    async def transfer_chat(self, session: AsyncSession, chat_id: int, new_support_id: int, from_support_id: int,
                            reason_id: Optional[int] = None):
        """
        Перевод чата на другого оператора/юриста:
          - сохраняем старый support в SupportHistoryChat
          - обновляем chats.user_support_id
          - добавляем ChatParticipant с ролью support/lawyer
          - помечаем left_at у предыдущего участника
        """
        # получаем чат
        q = select(Chat).where(Chat.id == chat_id)
        chat = (await session.execute(q)).scalars().first()
        if not chat:
            raise ValueError("Чат не найден")

        # history
        hist_date = SupportHistoryDate(date_join=datetime.utcnow())
        session.add(hist_date)
        await session.flush()

        hist = SupportHistoryChat(chat_id=chat.id, old_support_id=from_support_id, reason_id=reason_id,
                                  history_date_id=hist_date.id)
        session.add(hist)

        # помечаем left_at у активного участника support (если есть)
        q2 = select(ChatParticipant).where(ChatParticipant.chat_id == chat.id,
                                           ChatParticipant.role.in_(["support", "lawyer"]),
                                           ChatParticipant.left_at.is_(None))
        prev = (await session.execute(q2)).scalars().all()
        for p in prev:
            p.left_at = datetime.utcnow()
            session.add(p)

        # добавляем нового участника
        new_part = ChatParticipant(chat_id=chat.id, user_id=new_support_id, role="support")
        session.add(new_part)

        # обновляем chats
        chat.user_support_id = new_support_id
        session.add(chat)
        await session.commit()
        return chat

    @connection
    async def close_chat(self, session: AsyncSession, chat_id: int, closed_by_user_id: int, reason_id: Optional[int] = None):
        q = select(Chat).where(Chat.id == chat_id)
        chat = (await session.execute(q)).scalars().first()
        if not chat:
            raise ValueError("Чат не найден")

        chat.active = False
        chat.resolved = True
        chat.date_close = datetime.utcnow()
        session.add(chat)

        hist_date = SupportHistoryDate(date_join=datetime.utcnow(), date_leave=datetime.utcnow())
        session.add(hist_date)
        await session.flush()
        hist = SupportHistoryChat(chat_id=chat.id, old_support_id=closed_by_user_id, reason_id=reason_id,
                                  history_date_id=hist_date.id)
        session.add(hist)
        await session.commit()
        return chat

    @connection
    async def get_chats_for_lawyer(self, session: AsyncSession, lawyer_id: int) -> List[Chat]:
        # Возвращаем чаты клиентов, закреплённых за юристом
        q = select(Chat).join(ClientLawyerAssignment, ClientLawyerAssignment.client_id == Chat.user_id).where(
            ClientLawyerAssignment.lawyer_id == lawyer_id)
        res = await session.execute(q)
        return res.scalars().all()

    @connection
    async def get_chat_by_id(self, session: AsyncSession, chat_id: int) -> Optional[Chat]:
        """Получение чата по ID"""
        q = select(Chat).where(Chat.id == chat_id)
        res = await session.execute(q)
        return res.scalars().first()

    @connection
    async def update_chat_operator(self, session: AsyncSession, chat_id: int, operator_id: int):
        """Обновление оператора чата"""
        q = update(Chat).where(Chat.id == chat_id).values(user_support_id=operator_id)
        await session.execute(q)
        await session.commit()

    @connection
    async def add_chat_participant(self, session: AsyncSession, chat_id: int, user_id: int, role: str) -> ChatParticipant:
        """Добавление участника в чат"""
        participant = ChatParticipant(chat_id=chat_id, user_id=user_id, role=role)
        session.add(participant)
        await session.commit()
        await session.refresh(participant)
        return participant

    @connection
    async def mark_chat_participant_left(self, session: AsyncSession, chat_id: int, user_id: int):
        """Отметка ухода участника из чата"""
        q = update(ChatParticipant).where(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == user_id,
            ChatParticipant.left_at.is_(None)
        ).values(left_at=datetime.utcnow())
        await session.execute(q)
        await session.commit()

    @connection
    async def get_active_lawyer_chat(self, session: AsyncSession, client_id: int, lawyer_id: int) -> Optional[Chat]:
        """Получение активного чата клиента с юристом"""
        q = select(Chat).where(
            Chat.user_id == client_id,
            Chat.user_support_id == lawyer_id,
            Chat.active == True
        )
        res = await session.execute(q)
        return res.scalars().first()

    @connection
    async def create_lawyer_assignment(self, session: AsyncSession, client_id: int, lawyer_id: int) -> ClientLawyerAssignment:
        """Создание назначения юриста клиенту"""
        assignment = ClientLawyerAssignment(client_id=client_id, lawyer_id=lawyer_id)
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)
        return assignment

    @connection
    async def get_active_lawyer_assignment(self, session: AsyncSession, client_id: int) -> Optional[ClientLawyerAssignment]:
        """Получение активного назначения юриста для клиента"""
        q = select(ClientLawyerAssignment).where(
            ClientLawyerAssignment.client_id == client_id,
            ClientLawyerAssignment.unassigned_at.is_(None)
        )
        res = await session.execute(q)
        return res.scalars().first()


chat_db = ChatSupport()
