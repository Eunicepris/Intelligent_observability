"""
Dashboard Streamlit pour la plateforme de détection d'anomalies.

Interface visuelle qui permet de :
- Analyser une fenêtre spécifique
- Consulter l'historique des alertes
- Voir les statistiques globales
"""
import os
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from pathlib import Path



# CONFIGURATION



API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Détection d'anomalies",
    page_icon="🔍",
    layout="wide",
)



# EN-TÊTE


st.title("🔍 Plateforme de détection d'anomalies")
st.markdown(
    "Détection multi-modale d'anomalies dans les systèmes microservices — "
    "**Train Ticket** et **Online Boutique**"
)



# SIDEBAR — Configuration


st.sidebar.header("⚙️ Configuration")

# Système
systeme = st.sidebar.selectbox(
    "Système",
    ["train_ticket", "online_boutique"],
    format_func=lambda x: "Train Ticket" if x == "train_ticket" else "Online Boutique",
)

# Date
if systeme == "train_ticket":
    dates_dispo = ["2023-01-29", "2023-01-30"]
else:
    dates_dispo = ["2022-08-22", "2022-08-23"]

date = st.sidebar.selectbox("Date", dates_dispo)

# Fenêtre
window = st.sidebar.text_input(
    "Fenêtre (HH_MM)",
    value="08_43",
    help="Format : heure_minute — ex 08_43 pour 08:43"
)

# Info système
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 État du système")
try:
    r_health = requests.get(f"{API_URL}/api/health", timeout=2)
    if r_health.ok:
        st.sidebar.success("✓ API opérationnelle")
    else:
        st.sidebar.error("✗ API en erreur")
except requests.RequestException:
    st.sidebar.error("✗ API inaccessible")
    st.sidebar.info("Lancez : `uvicorn api.main:app --reload`")



# ONGLETS PRINCIPAUX


tab_detection, tab_alertes, tab_stats = st.tabs([
    "🎯 Détection",
    "🚨 Alertes",
    "📈 Statistiques",
])


# 
# ONGLET 1 : DÉTECTION
# 
with tab_detection:
    st.header("Analyse d'une fenêtre")
    
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.metric("Système", "TT" if systeme == "train_ticket" else "OB")
    with col_info2:
        st.metric("Date", date)
    with col_info3:
        st.metric("Fenêtre", window)
    
    if st.button("🚀 Lancer l'analyse", type="primary", use_container_width=True):
        with st.spinner("Analyse en cours..."):
            try:
                r = requests.post(
                    f"{API_URL}/api/detecter",
                    json={"systeme": systeme, "date": date, "window": window},
                    timeout=30,
                )
                
                if r.ok:
                    res = r.json()
                    
                    st.markdown("---")
                    st.subheader("📋 Résultat")
                    
                    # Statut principal
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        sev = res['severite']
                        if sev == 'CRITICAL':
                            st.error(f"🚨 {sev}")
                        elif sev == 'WARNING':
                            st.warning(f"⚠️ {sev}")
                        elif sev == 'LOW':
                            st.info(f"💡 {sev}")
                        else:
                            st.success(f"✓ {sev}")
                    
                    with col2:
                        conf_pct = res['confiance'] * 100
                        st.metric("Confiance", f"{conf_pct:.0f}%")
                    
                    with col3:
                        st.metric("Anomalie", "OUI" if res['anomalie'] else "NON")
                    
                    # Modalités
                    st.markdown("### Détection par modalité")
                    mod = res['modalites']
                    
                    col_m1, col_m2, col_m3 = st.columns(3)
                    with col_m1:
                        st.metric("Métriques (LOF)", "✓ Détecte" if mod['metriques'] else "○ Normal")
                    with col_m2:
                        st.metric("Logs (TF-IDF)", "✓ Détecte" if mod['logs'] else "○ Normal")
                    with col_m3:
                        st.metric("Traces (IF)", "✓ Détecte" if mod['traces'] else "○ Normal")
                    
                    # Graphique des modalités
                    df_mod = pd.DataFrame([
                        {"Modalité": "Métriques", "Détecte": 1 if mod['metriques'] else 0},
                        {"Modalité": "Logs"     , "Détecte": 1 if mod['logs']      else 0},
                        {"Modalité": "Traces"   , "Détecte": 1 if mod['traces']    else 0},
                    ])
                    
                    fig = px.bar(
                        df_mod,
                        x="Modalité",
                        y="Détecte",
                        color="Détecte",
                        color_continuous_scale=["#4CAF50", "#F44336"],
                        range_y=[0, 1.1],
                        title="Détection par modalité (1 = détecte, 0 = normal)",
                    )
                    fig.update_layout(showlegend=False, height=300)
                    st.plotly_chart(fig, use_container_width=True)


                    # ─── Type de panne prédit ───
                    if res.get('type_panne'):
                        tp = res['type_panne']
                        st.markdown("### 🔍 Type de panne prédit")
                        
                        col_tp1, col_tp2 = st.columns(2)
                        with col_tp1:
                            st.metric("Type de panne", tp['type_predit'].upper())
                        with col_tp2:
                            st.metric("Confiance classification", f"{tp['confiance']*100:.0f}%")
                        
                        # Action spécifique
                        st.info(f"**Action spécifique** : {tp['action_specifique']}")
                        
                        # Graphique probabilités
                        df_probs = pd.DataFrame([
                            {"Type": k, "Probabilité (%)": v * 100}
                            for k, v in tp['probabilites'].items()
                        ]).sort_values("Probabilité (%)", ascending=True)
                        
                        fig_probs = px.bar(
                            df_probs,
                            x="Probabilité (%)",
                            y="Type",
                            orientation='h',
                            color="Probabilité (%)",
                            color_continuous_scale='Blues',
                            title="Probabilités par type de panne",
                        )
                        fig_probs.update_layout(showlegend=False, height=350)
                        st.plotly_chart(fig_probs, use_container_width=True)

                        
                    # Action recommandée
                    st.markdown("### 🎬 Action recommandée")
                    if sev == 'CRITICAL':
                        st.error(res['action'])
                    elif sev == 'WARNING':
                        st.warning(res['action'])
                    elif sev == 'LOW':
                        st.info(res['action'])
                    else:
                        st.success(res['action'])
                
                else:
                    st.error(f"Erreur API : {r.status_code}")
                    st.json(r.json())
            
            except requests.RequestException as e:
                st.error(f"Erreur de connexion : {str(e)}")


# 
# ONGLET 2 : ALERTES
# 
with tab_alertes:
    st.header("Historique des alertes")
    
    col_filt1, col_filt2, col_filt3 = st.columns(3)
    
    with col_filt1:
        filtre_sev = st.selectbox(
            "Filtre sévérité",
            ["Toutes", "CRITICAL", "WARNING", "LOW", "NORMAL"],
        )
    
    with col_filt2:
        filtre_syst = st.selectbox(
            "Filtre système",
            ["Tous", "train_ticket", "online_boutique"],
        )
    
    with col_filt3:
        limite = st.number_input("Nb max", min_value=1, max_value=1000, value=50)
    
    try:
        params = {"limite": limite}
        if filtre_sev != "Toutes":
            params["severite"] = filtre_sev
        if filtre_syst != "Tous":
            params["systeme"] = filtre_syst
        
        r = requests.get(f"{API_URL}/api/alertes", params=params, timeout=10)
        
        if r.ok:
            data = r.json()
            alertes = data['alertes']
            
            st.markdown(f"**{data['total']}** alertes trouvées")
            
            if alertes:
                df = pd.DataFrame(alertes)
                
                # Résumé par sévérité
                col_a, col_b, col_c, col_d = st.columns(4)
                for niveau, col in [
                    ('CRITICAL', col_a),
                    ('WARNING' , col_b),
                    ('LOW'     , col_c),
                    ('NORMAL'  , col_d),
                ]:
                    nb = (df['severite'] == niveau).sum() if 'severite' in df.columns else 0
                    with col:
                        st.metric(niveau, nb)
                
                # Tableau
                cols_visibles = ['timestamp', 'systeme', 'fenetre', 'severite', 'confiance']
                cols_dispo = [c for c in cols_visibles if c in df.columns]
                st.dataframe(df[cols_dispo], use_container_width=True)
            else:
                st.info("Aucune alerte correspondant aux filtres")
        else:
            st.error(f"Erreur API : {r.status_code}")
    
    except requests.RequestException as e:
        st.error(f"Erreur : {str(e)}")


# 
# ONGLET 3 : STATISTIQUES
# 
with tab_stats:
    st.header("Statistiques globales")
    
    try:
        r = requests.get(f"{API_URL}/api/statistiques", timeout=10)
        
        if r.ok:
            stats = r.json()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Total")
                st.metric("Alertes enregistrées", stats['total'])
            
            with col2:
                st.subheader("Par système")
                for syst, nb in stats['par_systeme'].items():
                    st.metric(syst, nb)
            
            # Graphique par sévérité
            st.subheader("Distribution par sévérité")
            df_sev = pd.DataFrame([
                {"Sévérité": k, "Nombre": v}
                for k, v in stats['par_severite'].items()
            ])
            
            fig = px.bar(
                df_sev,
                x="Sévérité",
                y="Nombre",
                color="Sévérité",
                color_discrete_map={
                    'CRITICAL': '#E53935',
                    'WARNING' : '#FB8C00',
                    'LOW'     : '#1E88E5',
                    'NORMAL'  : '#43A047',
                },
                title="Alertes par niveau de sévérité",
            )
            st.plotly_chart(fig, use_container_width=True)
        
        else:
            st.error(f"Erreur API : {r.status_code}")
    
    except requests.RequestException as e:
        st.error(f"Erreur : {str(e)}")



# FOOTER


st.markdown("---")
st.caption(
    "Plateforme de détection d'anomalies — "
    "Projet de maîtrise en génie logiciel"
)