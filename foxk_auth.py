
import streamlit as st
from supabase import create_client


def get_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_ANON_KEY"],
    )


def require_vip():
    db = get_supabase()

    st.sidebar.markdown("### FOXK ACCOUNT")

    if "foxk_session" not in st.session_state:
        st.session_state.foxk_session = None

    session = st.session_state.foxk_session

    if session is None:
        st.title("FOXK / MEMBER LOGIN")

        login_tab, signup_tab = st.tabs(
            ["Log In", "Create Account"]
        )

        with login_tab:
            with st.form("foxk_login"):
                email = st.text_input("Email")
                password = st.text_input(
                    "Password", type="password"
                )
                submitted = st.form_submit_button("Log In")

                if submitted:
                    try:
                        result = db.auth.sign_in_with_password({
                            "email": email,
                            "password": password,
                        })
                        st.session_state.foxk_session = result.session
                        st.rerun()
                    except Exception:
                        st.error("Login failed. Check your credentials.")

        with signup_tab:
            with st.form("foxk_signup"):
                email = st.text_input("Email address")
                password = st.text_input(
                    "Create password", type="password"
                )
                submitted = st.form_submit_button(
                    "Create FOXK Account"
                )

                if submitted:
                    try:
                        db.auth.sign_up({
                            "email": email,
                            "password": password,
                        })
                        st.success(
                            "Check your email to verify your account, "
                            "then log in."
                        )
                    except Exception as error:
                        st.error(f"Signup failed: {error}")

        st.stop()

    try:
        db.auth.set_session(
            session.access_token,
            session.refresh_token,
        )
        user_response = db.auth.get_user()
        user = user_response.user

        if not user or not user.email_confirmed_at:
            st.warning("Please verify your email before continuing.")
            st.stop()

        st.sidebar.write(f"Logged in: {user.email}")

        if st.sidebar.button("Log Out"):
            db.auth.sign_out()
            st.session_state.foxk_session = None
            st.rerun()

        membership = (
            db.table("vip_members")
            .select("status,access_expires_at")
            .eq("user_id", user.id)
            .maybe_single()
            .execute()
        )

        record = membership.data

        from datetime import datetime, timezone

        active = False

        if record:
            expires = record.get("access_expires_at")
            if expires:
                expiry = datetime.fromisoformat(
                    expires.replace("Z", "+00:00")
                )
                active = (
                    record.get("status") in ("active", "trialing")
                    and expiry > datetime.now(timezone.utc)
                )

        if not active:
            st.title("FOXK / VIP ACCESS")
            st.warning("An active FOXK VIP membership is required.")
            st.link_button(
                "Get FOXK VIP — $10/week",
                "https://whop.com/discord-gg-50b0/foxk-vip-picks/",
            )
            st.stop()

        st.sidebar.success("FOXK VIP ACTIVE")

    except Exception:
        st.session_state.foxk_session = None
        st.error("Your login session expired. Please log in again.")
        st.stop()
