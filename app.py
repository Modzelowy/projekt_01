import streamlit as st
import pandas as pd # Choć conn.query zwraca DataFrame, import może być przydatny
from sqlalchemy import text # Import funkcji text

# --- Konfiguracja Połączenia (Streamlit sam odczyta z.streamlit/secrets.toml) ---
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error(f"Nie udało się połączyć z bazą danych. Sprawdź konfigurację w.streamlit/secrets.toml i czy Docker z Postgresem działa.")
    st.error(f"Błąd: {e}")
    st.stop() # Zakończ działanie aplikacji, jeśli nie ma połączenia

# --- Funkcja do tworzenia tabeli ---
def stworz_tabele_jesli_nie_istnieje():
    try:
        with conn.session as s:
            s.execute(text("""
                CREATE TABLE IF NOT EXISTS ulubione_rzeczy (
                    id SERIAL PRIMARY KEY,
                    nazwa VARCHAR(255) NOT NULL,
                    opis TEXT
                );
            """))
            s.commit()
    except Exception as e:
        st.error(f"Błąd podczas tworzenia tabeli: {e}")

# Wywołanie funkcji tworzenia tabeli przy starcie aplikacji
stworz_tabele_jesli_nie_istnieje()

# --- Główny Interfejs Aplikacji ---
st.title("Moja Lista Ulubionych Rzeczy")

# --- Sekcja CREATE (Dodawanie nowych rzeczy) ---
with st.expander("📝 Dodaj nową ulubioną rzecz", expanded=False):
    with st.form("formularz_dodawania", clear_on_submit=True):
        nazwa_nowej_rzeczy = st.text_input("Nazwa rzeczy:")
        opis_nowej_rzeczy = st.text_area("Opis rzeczy:")
        przycisk_dodaj = st.form_submit_button("Dodaj rzecz")

        if przycisk_dodaj:
            if nazwa_nowej_rzeczy:
                try:
                    with conn.session as s:
                        s.execute(
                            text('INSERT INTO ulubione_rzeczy (nazwa, opis) VALUES (:nazwa_param, :opis_param);'),
                            params=dict(nazwa_param=nazwa_nowej_rzeczy, opis_param=opis_nowej_rzeczy)
                        )
                        s.commit()
                    st.success(f"Dodano do ulubionych: '{nazwa_nowej_rzeczy}'!")
                except Exception as e:
                    st.error(f"Błąd podczas dodawania rzeczy: {e}")
            else:
                st.warning("Nazwa rzeczy nie może być pusta.")

# --- Sekcja READ (Wyświetlanie listy rzeczy) ---
st.header("📖 Moje Ulubione Rzeczy")
try:
    # Omijamy conn.query, aby uniknąć problemu z hashowaniem obiektu text()
    with conn.session as s:
        ulubione_rzeczy_df = pd.read_sql(text('SELECT id, nazwa, opis FROM ulubione_rzeczy ORDER BY id DESC;'), s.connection())

    if not ulubione_rzeczy_df.empty:
        # Użycie st.data_editor zamiast st.dataframe pozwala na edycję (choć tu nie implementujemy zapisu zmian)
        # Dla prostego wyświetlania st.dataframe(ulubione_rzeczy_df, use_container_width=True, hide_index=True) też jest OK.
        st.dataframe(
            ulubione_rzeczy_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "nazwa": st.column_config.TextColumn("Nazwa"),
                "opis": st.column_config.TextColumn("Opis")
            }
        )
    else:
        st.info("Nie masz jeszcze żadnych ulubionych rzeczy. Dodaj coś w sekcji powyżej!")
except Exception as e:
    st.error(f"Błąd podczas odczytu danych: {e}")
    # W razie błędu utwórz pusty DataFrame, aby uniknąć NameError w sekcji DELETE
    ulubione_rzeczy_df = pd.DataFrame()


# --- Sekcja DELETE (Usuwanie rzeczy) ---
st.header("🗑️ Usuń rzecz z listy")
if not ulubione_rzeczy_df.empty: # Używamy DataFrame'u pobranego w sekcji READ
    # Tworzymy słownik mapujący "ID: Nazwa" na samo ID dla łatwiejszego przetwarzania
    opcje_usuwania_dict = {f"{row.id}: {row.nazwa}": row.id for row in ulubione_rzeczy_df.itertuples()}
    
    if opcje_usuwania_dict: # Sprawdź, czy są jakieś opcje do usunięcia
        wybrana_opcja_str = st.selectbox(
            "Wybierz rzecz do usunięcia:",
            options=list(opcje_usuwania_dict.keys()) # Lista kluczy jako opcje
        )

        if st.button("Usuń wybraną rzecz", type="primary"): # type="primary" dla czerwonego przycisku
            if wybrana_opcja_str:
                id_rzeczy_do_usuniecia = opcje_usuwania_dict[wybrana_opcja_str]
                try:
                    with conn.session as s:
                        s.execute(
                            text('DELETE FROM ulubione_rzeczy WHERE id = :id_param;'),
                            params=dict(id_param=id_rzeczy_do_usuniecia)
                        )
                        s.commit()
                    st.success(f"Usunięto rzecz: '{wybrana_opcja_str.split(': ', 1)[1]}'!")
                    st.rerun() # Odśwież, aby zaktualizować listę
                except Exception as e:
                    st.error(f"Błąd podczas usuwania rzeczy: {e}")
            else:
                st.warning("Nie wybrano żadnej rzeczy do usunięcia.")
    else:
        st.info("Lista jest pusta, nie ma czego usuwać.")
else:
    st.info("Lista jest pusta, nie ma czego usuwać.")

