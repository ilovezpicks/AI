 
import streamlit as st
from datetime import datetime, timezone
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
        login_tab, signup_tab = st.tabs(["Log In", "Create Account"])

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
                            "email": email.strip(),
                            "password": password,
                        })

                        if result.session is None:
                            st.error(
                                "Please verify your email before logging in."
                            )
                        else:
                            st.session_state.foxk_session = result.session
                            st.rerun()

                    except Exception as error:
                        st.error(f"Login failed: {error}")

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
                            "email": email.strip(),
                            "password": password,
                        })
                        st.success(
                            "Check your email to verify your account, "
                            "then return here and log in."
                        )
                    except Exception as error:
                        st.error(f"Signup failed: {error}")

        st.stop()

    # Restore and refresh the authenticated session.
    try:
        refreshed = db.auth.set_session(
            session.access_token,
            session.refresh_token,
        )
        if refreshed.session is not None:
            st.session_state.foxk_session = refreshed.session

        user_response = db.auth.get_user()
        user = user_response.user

    except Exception as error:
        st.session_state.foxk_session = None
        st.error(f"FOXK LOGIN TEST 1030: {error}")
        st.stop()

    if not user:
        st.session_state.foxk_session = None
        st.error("Please log in again.")
        st.stop()

    if not user.email_confirmed_at:
        st.warning("Please verify your email before continuing.")
        st.stop()

    st.sidebar.write(f"Logged in: {user.email}")

    if st.sidebar.button("Log Out"):
        db.auth.sign_out()
        st.session_state.foxk_session = None
        st.rerun()

    # Check owner access.
    try:
        admin_result = (
            db.table("foxk_admins")
            .select("user_id")
            .eq("user_id", user.id)
            .maybe_single()
            .execute()
        )
    except Exception as error:
        st.error(f"Owner access check failed: {error}")
        st.stop()

    if admin_result.data:
        st.sidebar.success("FOXK OWNER ACCESS")
        return

    # Check VIP membership.
    try:
        membership = (
            db.table("vip_members")
            .select("status,access_expires_at")
            .eq("user_id", user.id)
            .maybe_single()
            .execute()
        )
    except Exception as error:
        st.error(f"VIP membership check failed: {error}")
        st.stop()

    record = membership.data
    active = False

    if record:
        expires = record.get("access_expires_at")
        if expires:
            try:
                expiry = datetime.fromisoformat(
                    expires.replace("Z", "+00:00")
                )
                active = (
                    record.get("status") in ("active", "trialing")
                    and expiry > datetime.now(timezone.utc)
                )
            except (ValueError, TypeError):
                active = False

    if not active:
        st.title("FOXK / VIP ACCESS")
        st.warning(
            "An active FOXK VIP membership is required."
        )
        st.link_button(
            "Get FOXK VIP — $10/week",
            "https://whop.com/discord-gg-50b0/foxk-vip-picks/",
        )
        st.stop()

    st.sidebar.success("FOXK VIP ACTIVE")
