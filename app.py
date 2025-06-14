import streamlit as st
import pandas as pd
from sqlalchemy import text # Import the text function

# --- Connection Setup (Streamlit reads from .streamlit/secrets.toml automatically) ---
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error(f"Failed to connect to the database. Check your configuration in .streamlit/secrets.toml and ensure the Postgres Docker container is running.")
    st.error(f"Error: {e}")
    st.stop() # Stop the app if the connection fails

# --- ONE-TIME DATA MIGRATION SCRIPT ---
# This script will run once to rename the old table and its columns to the new ones.
# After running the app once successfully, you can remove this block.
try:
    with conn.session as s:
        # Step 1: Check if the old table 'ulubione_rzeczy' exists and rename it
        result = s.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ulubione_rzeczy')"))
        if result.fetchone()[0]:
            st.warning("Migrating table name...")
            s.execute(text('DROP TABLE IF EXISTS favorite_things;')) # Drop empty new table if it exists
            s.execute(text('ALTER TABLE ulubione_rzeczy RENAME TO favorite_things;'))
            s.commit()
            st.success("Table renamed. Refreshing...")
            st.rerun()

        # Step 2: Check if old columns exist in 'favorite_things' and rename them
        result = s.execute(text("SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'favorite_things' AND column_name = 'nazwa')"))
        if result.fetchone()[0]:
            st.warning("Migrating column names...")
            s.execute(text('ALTER TABLE favorite_things RENAME COLUMN nazwa TO name;'))
            s.execute(text('ALTER TABLE favorite_things RENAME COLUMN opis TO description;'))
            s.commit()
            st.success("Columns renamed. Your data is fully restored. Refreshing...")
            st.rerun()

except Exception as e:
    st.error(f"An error occurred during data migration: {e}")
    st.stop()


# --- Function to create the table ---
def create_table_if_not_exists():
    try:
        with conn.session as s:
            s.execute(text("""
                CREATE TABLE IF NOT EXISTS favorite_things (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    description TEXT
                );
            """))
            s.commit()
    except Exception as e:
        st.error(f"Error while creating table: {e}")

# Call the table creation function on app startup
create_table_if_not_exists()

# --- Main Application Interface ---
st.title("My Favorite Things List")

# --- CREATE Section (Adding new things) ---
with st.expander(" Add a new favorite thing", expanded=False):
    with st.form("add_form", clear_on_submit=True):
        new_thing_name = st.text_input("Thing name:")
        new_thing_description = st.text_area("Thing description:")
        add_button = st.form_submit_button("Add Thing")

        if add_button:
            if new_thing_name:
                try:
                    with conn.session as s:
                        s.execute(
                            text('INSERT INTO favorite_things (name, description) VALUES (:name_param, :desc_param);'),
                            params=dict(name_param=new_thing_name, desc_param=new_thing_description)
                        )
                        s.commit()
                    st.success(f"Added to favorites: '{new_thing_name}'!")
                except Exception as e:
                    st.error(f"Error while adding thing: {e}")
            else:
                st.warning("Thing name cannot be empty.")

# --- READ Section (Displaying the list of things) ---
st.header(" My Favorite Things")
try:
    # We bypass conn.query to avoid the hashing issue with the text() object
    with conn.session as s:
        favorite_things_df = pd.read_sql(text('SELECT id, name, description FROM favorite_things ORDER BY id DESC;'), s.connection())

    if not favorite_things_df.empty:
        st.dataframe(
            favorite_things_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "name": st.column_config.TextColumn("Name"),
                "description": st.column_config.TextColumn("Description")
            }
        )
    else:
        st.info("You don't have any favorite things yet. Add something in the section above!")
except Exception as e:
    st.error(f"Error while reading data: {e}")
    # In case of an error, create an empty DataFrame to avoid a NameError in the DELETE section
    favorite_things_df = pd.DataFrame()


# --- DELETE Section (Removing things) ---
st.header(" Remove thing from list")
if not favorite_things_df.empty: # We use the DataFrame fetched in the READ section
    # Create a dictionary mapping "ID: Name" to just the ID for easier processing
    delete_options_dict = {f"{row.id}: {row.name}": row.id for row in favorite_things_df.itertuples()}
    
    if delete_options_dict: # Check if there are any options to remove
        selected_option_str = st.selectbox(
            "Select a thing to remove:",
            options=list(delete_options_dict.keys()) # List of keys as options
        )

        if st.button("Remove Selected Thing", type="primary"): # type="primary" for a red button
            if selected_option_str:
                thing_id_to_delete = delete_options_dict[selected_option_str]
                try:
                    with conn.session as s:
                        s.execute(
                            text('DELETE FROM favorite_things WHERE id = :id_param;'),
                            params=dict(id_param=thing_id_to_delete)
                        )
                        s.commit()
                    st.success(f"Removed thing: '{selected_option_str.split(': ', 1)[1]}'!")
                    st.rerun() # Rerun to refresh the list
                except Exception as e:
                    st.error(f"Error while removing thing: {e}")
            else:
                st.warning("No thing selected for removal.")
    else:
        st.info("The list is empty, nothing to remove.")
else:
    st.info("The list is empty, nothing to remove.")



# --- Developer Options (to be removed in production) ---
with st.expander(" Developer Options"):
    if st.button("HARD RESET DATABASE (will drop table)", type="primary"):
        try:
            with conn.session as s:
                s.execute(text('DROP TABLE IF EXISTS favorite_things;'))
                s.commit()
            st.success("Table 'favorite_things' has been dropped.")
            st.info("Refresh the page (F5) to restart the app and recreate the table.")
            st.stop()
        except Exception as e:
            st.error(f"Error while resetting the database: {e}")
