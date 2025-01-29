from datetime import datetime, timedelta
import csv
from zoneinfo import ZoneInfo
from functools import reduce
from pymongo import MongoClient
from bson.codec_options import CodecOptions


TZ = ZoneInfo("Asia/Kolkata")
# DATABASE_CONNECTIONS__MONGODB_CONNECTION__URI = "mongodb://dbadmin:WgF8i17BVrhMveS@c.hfcl-genai-cosmon-cin-001-uat.privatelink.mongocluster.cosmos.azure.com:10260/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000"
DATABASE_CONNECTIONS__MONGODB_CONNECTION__URI = "mongodb+srv://dbadmin:WgF8i17BVrhMveS@hfcl-genai-cosmon-cin-001-uat.mongocluster.cosmos.azure.com/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000"
SESSION__STORE = "sessions"


class MongoDBConnection:
    def __init__(self, db_name: str):
        self.client = MongoClient(DATABASE_CONNECTIONS__MONGODB_CONNECTION__URI)
        self.db = self.client[db_name].with_options(
            codec_options=CodecOptions(tz_aware=True, tzinfo=TZ)
        )


def download_metrics(bot_name: str, start: str, end: str):
    mongodb_connection = MongoDBConnection(db_name=bot_name)
    session_store = mongodb_connection.db[SESSION__STORE]
    start_date = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=TZ)
    end_date = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=TZ)

    sessions = session_store.aggregate(
        [
            {
                "$match": {
                    "created_at": {
                        "$gte": start_date,
                        "$lt": end_date + timedelta(days=1),
                    }
                }
            },
            {"$count": "count"},
        ]
    ).to_list()

    consented_sessions = session_store.aggregate(
        [
            {
                "$match": {
                    "created_at": {
                        "$gte": start_date,
                        "$lt": end_date + timedelta(days=1),
                    }
                }
            },
            {"$match": {"terms_of_service_consent.is_consented": True}},
            {"$addFields": {"session_id": {"$toString": "$_id"}}},
            {
                "$lookup": {
                    "from": "chat_history",
                    "localField": "session_id",
                    "foreignField": "SessionId",
                    "as": "chat_history",
                }
            },
            {
                "$project": {
                    "data.access_token": 1,
                    "logout": 1,
                    "session_id": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "chat_history": {"_id": 1, "History": 1},
                }
            },
        ]
    ).to_list()

    chat_sessions = list(
        filter(
            lambda session: len(session["chat_history"]) > 2,
            consented_sessions,
        )
    )

    session_count = sessions[0]["count"]
    consented_session_count = len(consented_sessions)
    click_through_rate = round((consented_session_count / session_count) * 100, 2)
    chat_session_count = len(chat_sessions)
    total_chat_session_messages = reduce(
        lambda sum, session: sum + len(session["chat_history"]),
        chat_sessions,
        0,
    )
    avg_messages_count_per_chat_session = round(
        total_chat_session_messages / chat_session_count, 2
    )
    max_messages_in_a_chat_session = reduce(
        lambda max_len, session: max(len(session["chat_history"]), max_len),
        chat_sessions,
        0,
    )
    total_chat_minutes = int(
        reduce(
            lambda sum, session: sum
            + (
                session["chat_history"][len(session["chat_history"]) - 1][
                    "_id"
                ].generation_time
                - session["chat_history"][0]["_id"].generation_time
            ).total_seconds(),
            chat_sessions,
            0,
        )
        / 60.0
    )
    total_chat_hours = round(total_chat_minutes / 60.0, 2)
    avg_length_per_chat_session_in_minutes = round(
        total_chat_minutes / chat_session_count, 2
    )
    max_length_of_a_chat_session_in_minutes = int(
        reduce(
            lambda max_len, session: max(
                (
                    session["chat_history"][len(session["chat_history"]) - 1][
                        "_id"
                    ].generation_time
                    - session["chat_history"][0]["_id"].generation_time
                ).total_seconds(),
                max_len,
            ),
            chat_sessions,
            0,
        )
        / 60.0
    )
    otp_logged_in_chat_sessions = list(
        filter(
            lambda session: session["data"].get("access_token", None),
            chat_sessions,
        )
    )
    otp_logged_in_chat_session_count = len(otp_logged_in_chat_sessions)
    manually_logged_out_chat_sessions = list(
        filter(
            lambda session: session["logout"],
            chat_sessions,
        )
    )
    manually_logged_out_chat_session_count = len(manually_logged_out_chat_sessions)

    filename = f"H.Ai_Chat_Metrics_{start_date.strftime('%Y_%m_%d')}-{end_date.strftime('%Y_%m_%d')}.csv"

    with open(filename, "w", newline="") as csvfile:
        fieldnames = ["Metric", "Value", "Remarks"]

        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(
            [
                {
                    "Metric": "Total unique sessions",
                    "Value": session_count,
                    "Remarks": "Number of unique sessions created for showing chatbot button on website",
                },
                {
                    "Metric": "Total user consented sessions",
                    "Value": consented_session_count,
                    "Remarks": "Number of sessions where user consented to Terms of Service to use the bot",
                },
                {
                    "Metric": "Click Through Rate (CTR) (in %)",
                    "Value": click_through_rate,
                    "Remarks": "Percentage of users consented to initiate chat out of total chatbot button views",
                },
                {
                    "Metric": "Total chat sessions",
                    "Value": chat_session_count,
                    "Remarks": "Sessions where users initiated the chat by prompting at least once",
                },
                {
                    "Metric": "Total chat session messages",
                    "Value": total_chat_session_messages,
                    "Remarks": "Total number of chat messages in all the chat sessions",
                },
                {
                    "Metric": "Average messages per chat session",
                    "Value": avg_messages_count_per_chat_session,
                    "Remarks": "Average number of chat messages in a single chat session",
                },
                {
                    "Metric": "Maximum messages in a single chat session",
                    "Value": max_messages_in_a_chat_session,
                    "Remarks": "Maximum number of chat messages in a single chat session",
                },
                {
                    "Metric": "Total engagement time (in minutes)",
                    "Value": total_chat_minutes,
                    "Remarks": "Total time spend by all the users across all the chat sessions to interact with the bot",
                },
                {
                    "Metric": "Total engagement time (in hours)",
                    "Value": total_chat_hours,
                    "Remarks": "-",
                },
                {
                    "Metric": "Average engagement time per chat session (in minutes)",
                    "Value": avg_length_per_chat_session_in_minutes,
                    "Remarks": "Average time spend by a user chatting with the bot",
                },
                {
                    "Metric": "Maximum engagement time in a single chat session (in minutes)",
                    "Value": max_length_of_a_chat_session_in_minutes,
                    "Remarks": "Maximum time spend by a user in a single chat session with the bot",
                },
                {
                    "Metric": "OTP logged in chat sessions",
                    "Value": otp_logged_in_chat_session_count,
                    "Remarks": "Number of sessions where user logged in via OTP auth to fetch the info",
                },
                {
                    "Metric": "Manually logged out chat sessions",
                    "Value": manually_logged_out_chat_session_count,
                    "Remarks": "Number of sessions where user manually logged out by clicking the logout button",
                },
            ]
        )

    print("done")


download_metrics("HAiBot", "2024-12-01", "2025-01-31")
