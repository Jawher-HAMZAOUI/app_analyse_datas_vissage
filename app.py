import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import pdfkit
import tempfile
import base64

# Charger la configuration depuis le fichier JSON
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# Configurer la page Streamlit
st.set_page_config(page_title=config["app_title"], layout="wide", page_icon=config["page_icon"])

# Palette de couleurs depuis la config
palette_name = config["plot_colors"]["main_palette"]
color_sequence = getattr(px.colors.qualitative, palette_name)

# Appliquer le CSS depuis la config
st.markdown(f"""
<style>
    body {{
        font-family: {config["css_style"]["font"]};
        color: {config["css_style"]["text_color"]};
        background-color: {config["css_style"]["background_color"]};
    }}
    .block-container {{
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: {config["css_style"]["max_width"]};
        margin-left: auto;
        margin-right: auto;
    }}
    .stSidebar {{
        background-color: {config["css_style"]["sidebar_background"]};
        padding: 1rem 1.5rem;
        border-radius: 10px;
        font-size: 14px;
    }}
</style>
""", unsafe_allow_html=True)

# Titre de l'application
st.title(config["app_title"])

# Upload de fichier
uploaded_file = st.file_uploader("Charger un fichier Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, engine="openpyxl")

    # Nettoyage
    df.columns = df.columns.str.strip()
    df["Result."] = df["Result."].astype(str).str.strip()
    df["Prog."] = df["Prog."].astype(str).str.strip()

    # Sidebar : filtres
    with st.sidebar:
        st.header("Filtres")
        selected_results = st.multiselect("Résultat", options=df["Result."].unique(), default=df["Result."].unique())
        selected_prog = st.multiselect("Programme", options=df["Prog."].unique(), default=df["Prog."].unique())

    df_filtered = df[(df["Result."].isin(selected_results)) & (df["Prog."].isin(selected_prog))]

    # KPIs
    st.markdown("---")
    st.subheader("Résumé rapide")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Lignes filtrées", len(df_filtered))
    col2.metric("Non conformes", len(df_filtered[df_filtered["Result."].str.contains("ERR|W|L|T", case=False, na=False)]))
    col3.metric("M[Nm] Moyenne", f"{df_filtered['M[Nm]'].mean():.2f}")
    col4.metric("T[s] Moyenne", f"{df_filtered['T[s]'].mean():.2f}")

    st.markdown("---")

    # Graphiques 2x2
    st.subheader("Visualisations:")

    numeric_cols = config["numeric_columns"]
    cols_to_plot = config["default_tabs"]
    tabs = st.tabs([f" {col}" for col in cols_to_plot])

    for tab, column_name in zip(tabs, cols_to_plot):
        with tab:
            st.markdown(f"### Distribution de **{column_name}** par Programme")

            fig = px.box(
                df_filtered,
                x="Prog.",
                y=column_name,
                color="Prog.",
                points="outliers",
                color_discrete_sequence=color_sequence
            )

            moyenne_par_prog = df_filtered.groupby("Prog.")[column_name].mean().reset_index()
            fig.add_trace(go.Scatter(
                x=moyenne_par_prog["Prog."],
                y=moyenne_par_prog[column_name],
                mode='lines+markers',
                name=f"Moyenne {column_name}",
                line=dict(color=config["plot_colors"]["trendline"]["color"],
                          dash=config["plot_colors"]["trendline"]["style"]),
                marker=dict(size=7)
            ))

            fig.update_layout(showlegend=False, margin=dict(t=30, b=20, l=20, r=20), height=400)
            st.plotly_chart(fig, use_container_width=True)

    # Graphique relation entre variables
    st.markdown("---")
    st.subheader("Relations entre variables numériques")

    all_numeric_cols = numeric_cols
    x_var = st.selectbox("Variable X", all_numeric_cols, index=all_numeric_cols.index(config["x_y_defaults"]["x"]))
    y_var = st.selectbox("Variable Y", all_numeric_cols, index=all_numeric_cols.index(config["x_y_defaults"]["y"]))

    if x_var == y_var:
        st.warning("Veuillez sélectionner deux variables différentes pour afficher la relation.")
    else:
        fig_rel = px.scatter(
            df_filtered,
            x=x_var,
            y=y_var,
            color="Prog.",
            trendline="ols",
            title=f"Relation entre {x_var} et {y_var} par Programme",
            color_discrete_sequence=color_sequence
        )
        st.plotly_chart(fig_rel, use_container_width=True)

    # COURBES DE PROGRESSION
    st.markdown("---")
    st.subheader("📈 Courbes")

    x_var = st.selectbox(
        "Variable X",
        all_numeric_cols,
        index=all_numeric_cols.index(config["x_y_defaults"]["x"]),
        key="x_curve"
    )

    y_var = st.selectbox(
        "Variable Y",
        all_numeric_cols,
        index=all_numeric_cols.index(config["x_y_defaults"]["y"]),
        key="y_curve"
    )

    if x_var == y_var:
        st.warning("Veuillez sélectionner deux variables différentes pour afficher la courbe.")
    else:
        st.markdown(f"### Évolution de **{y_var}** en fonction de **{x_var}**")

        # Tri pour une courbe fluide
        df_sorted = df_filtered.sort_values(by=x_var)

        fig_line = go.Figure()

        for prog in df_sorted["Prog."].unique():
            df_prog = df_sorted[df_sorted["Prog."] == prog]

            fig_line.add_trace(go.Scatter(
                x=df_prog[x_var],
                y=df_prog[y_var],
                mode="lines+markers",
                name=str(prog),
                line=dict(width=2),
                marker=dict(size=4)
            ))

        fig_line.update_layout(
            xaxis_title=x_var,
            yaxis_title=y_var,
            template="plotly_white",
            height=450,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=40, b=20)
        )

        st.plotly_chart(fig_line, use_container_width=True)

    # SECTION : Affichage uniquement des courbes avec sélection de X
    st.markdown("---")
    st.subheader("📈 Courbes des variables")

    x_var = st.selectbox(
        "Sélectionnez la variable à tracer",
        all_numeric_cols,
        index=all_numeric_cols.index(config["x_y_defaults"]["x"]),
        key="x_unique"
    )

    df_sorted = df_filtered.sort_values(by=x_var).reset_index(drop=True)
    df_sorted["Nb_Pieces"] = df_sorted.index + 1

    total_pieces = len(df_filtered)
    st.metric("Lignes filtrées", total_pieces)

    fig_lines = go.Figure()

    fig_lines.add_trace(go.Scatter(
        x=df_sorted["Nb_Pieces"],
        y=df_sorted[x_var],
        mode="lines+markers",
        name=x_var,
        line=dict(width=2),
        marker=dict(size=6)
    ))

    fig_lines.update_layout(
        title=f"Évolution de {x_var} en fonction du nombre total de pièces",
        xaxis_title="Nombre total de pièces",
        yaxis_title=x_var,
        template="plotly_white",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=50, b=20)
    )

    st.plotly_chart(fig_lines, use_container_width=True)
    st.markdown("---")

    # --- Génération du rapport PDF ---
    if st.button("📄 Générer le rapport PDF"):
        with st.spinner("Génération du rapport PDF en cours..."):

            # Générer contenu HTML du rapport
            html_content = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        margin: 20px;
                        color: #333;
                    }}
                    h1 {{
                        color: #0b5394;
                    }}
                    table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-top: 20px;
                        font-size: 12px;
                    }}
                    th, td {{
                        border: 1px solid #ccc;
                        padding: 6px;
                        text-align: left;
                    }}
                    th {{
                        background-color: #f2f2f2;
                    }}
                </style>
            </head>
            <body>
                <h1>{config["app_title"]}</h1>
                <h2>Résumé</h2>
                <ul>
                    <li>Lignes filtrées : {len(df_filtered)}</li>
                    <li>Non conformes : {len(df_filtered[df_filtered["Result."].str.contains("ERR|W|L|T", case=False, na=False)])}</li>
                    <li>M[Nm] moyenne : {df_filtered["M[Nm]"].mean():.2f}</li>
                    <li>T[s] moyenne : {df_filtered["T[s]"].mean():.2f}</li>
                </ul>
                <h2>Données filtrées</h2>
                {df_filtered.to_html(index=False, justify='center')}
            </body>
            </html>
            """

            # Création d'un fichier PDF temporaire
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                pdfkit.from_string(html_content, tmp_pdf.name)

                with open(tmp_pdf.name, "rb") as f:
                    base64_pdf = base64.b64encode(f.read()).decode('utf-8')

                href = f'<a href="data:application/pdf;base64,{base64_pdf}" download="rapport.pdf">📥 Cliquez ici pour télécharger le rapport PDF</a>'
                st.markdown(href, unsafe_allow_html=True)

else:
    st.info("💡 Veuillez charger un fichier Excel (.xlsx) pour démarrer.")
