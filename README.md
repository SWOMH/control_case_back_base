# control_case_back_base
Это база для бекенда приложения/сайта пользователей


erDiagram
    REASON_CLOSE_CHAT {
        int id PK
        string reason
    }

    CHAT {
        int id PK
        int user_id FK
        int user_support_id FK
        datetime date_created
        bool active
        bool resolved
        datetime date_close
    }

    CHAT_MESSAGE {
        int id PK
        int chat_id FK
        int sender_id FK
        string sender_type
        text message
        datetime created_at
        string status
        datetime edited_at
    }

    CHAT_ATTACHMENT {
        int id PK
        int message_id FK
        string filename
        string file_path
        string content_type
        int size
    }

    MESSAGE_READ_RECEIPT {
        int id PK
        int message_id FK
        int user_id FK
        datetime read_at
    }

    CHAT_PARTICIPANT {
        int id PK
        int chat_id FK
        int user_id FK
        string role
        datetime joined_at
        datetime left_at
    }

    SUPPORT_HISTORY_DATE {
        int id PK
        datetime date_join
        datetime date_leave
    }

    SUPPORT_HISTORY_CHAT {
        int id PK
        int chat_id FK
        int old_support_id FK
        int reason_id FK
        int history_date_id FK
    }

    CLIENT_LAWYER_ASSIGNMENT {
        int id PK
        int client_id FK
        int lawyer_id FK
        datetime assigned_at
        datetime unassigned_at
    }

    CHAT_RATING {
        int id PK
        int chat_id FK
        int rating
        text comment
        datetime created_at
    }

    REASON_CLOSE_CHAT ||--o{ SUPPORT_HISTORY_CHAT : "used_by"
    CHAT ||--o{ CHAT_MESSAGE : "has"
    CHAT ||--o{ CHAT_PARTICIPANT : "has"
    CHAT ||--o{ SUPPORT_HISTORY_CHAT : "history"
    CHAT ||--o{ CHAT_RATING : "has"
    CHAT_MESSAGE ||--o{ CHAT_ATTACHMENT : "has"
    CHAT_MESSAGE ||--o{ MESSAGE_READ_RECEIPT : "has"
    CHAT_MESSAGE }o--|| CHAT : "belongs_to"