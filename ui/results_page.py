import streamlit as st


def render_results(df):

    st.subheader("Scan Results")

    if df.empty:
        st.warning("No qualifying stocks found.")
        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )