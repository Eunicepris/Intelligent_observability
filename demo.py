"""
Démonstration du pipeline de détection d'anomalies.

Exécute une série de tests sur les 2 systèmes et affiche les résultats
de manière lisible.
"""
from pipeline.main import PipelineComplet, afficher_resultat


def bandeau(titre):
    """Affiche un bandeau titre."""
    print("\n" + "="*70)
    print(f"  {titre}")
    print("="*70)


def demo_train_ticket():
    """Démonstration sur Train Ticket."""
    bandeau("DÉMONSTRATION 1 — Train Ticket")
    
    print("\nInitialisation du pipeline...")
    pipeline = PipelineComplet(systeme='train_ticket')
    print("✓ Pipeline chargé (46 services)")
    
    # Test 1 : Panne return
    print("\n▶ Test 1.1 : Panne 'return' sur ts-contacts-service")
    resultat = pipeline.traiter_fenetre('2023-01-29', '08_43')
    afficher_resultat(resultat)
    
    # Test 2 : Panne exception
    print("\n▶ Test 1.2 : Autre fenêtre de panne")
    resultat = pipeline.traiter_fenetre('2023-01-29', '10_28')
    afficher_resultat(resultat)
    
    # Test 3 : Batch
    print("\n▶ Test 1.3 : Traitement en batch (5 fenêtres)")
    fenetres = [
        ('2023-01-29', '08_43'),
        ('2023-01-29', '08_44'),
        ('2023-01-29', '08_45'),
        ('2023-01-29', '11_06'),
        ('2023-01-29', '14_24'),
    ]
    resultats = pipeline.traiter_batch(fenetres)
    print(f"\n  {len(resultats)} fenêtres traitées :")
    for r in resultats:
        emoji = {'CRITICAL': '🚨', 'WARNING': '⚠️', 'LOW': '💡', 'NORMAL': '✓'}[r['severite']]
        print(f"    {emoji} {r['fenetre']} : {r['severite']} ({r['confiance']*100:.0f}%)")


def demo_online_boutique():
    """Démonstration sur Online Boutique."""
    bandeau("DÉMONSTRATION 2 — Online Boutique")
    
    print("\nInitialisation du pipeline...")
    pipeline = PipelineComplet(systeme='online_boutique')
    print("✓ Pipeline chargé (10 services)")
    
    # Test 1 : Panne cpu_contention
    print("\n▶ Test 2.1 : Panne 'cpu_contention' sur frontend")
    resultat = pipeline.traiter_fenetre('2022-08-22', '03_53')
    afficher_resultat(resultat)
    
    # Test 2 : Panne return
    print("\n▶ Test 2.2 : Panne 'return' sur frontend")
    resultat = pipeline.traiter_fenetre('2022-08-22', '04_02')
    afficher_resultat(resultat)


def demo_statistiques():
    """Affiche les statistiques globales."""
    bandeau("STATISTIQUES GLOBALES")
    
    from pipeline.alertes import SystemeAlertes
    alertes = SystemeAlertes()
    stats = alertes.statistiques()
    
    print(f"\n  Total alertes  : {stats['total']}")
    print(f"\n  Par sévérité :")
    for niveau, nb in stats['par_severite'].items():
        emoji = {'CRITICAL': '🚨', 'WARNING': '⚠️', 'LOW': '💡', 'NORMAL': '✓'}[niveau]
        print(f"    {emoji} {niveau:<10} : {nb}")
    
    print(f"\n  Par système :")
    for systeme, nb in stats['par_systeme'].items():
        print(f"    • {systeme:<20} : {nb}")


def main():
    """Point d'entrée principal."""
    print("\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█" + "  DÉMONSTRATION — Pipeline de détection d'anomalies".ljust(68) + "█")
    print("█" + "  Fusion multi-modale : métriques + logs + traces".ljust(68) + "█")
    print("█" + " "*68 + "█")
    print("█"*70)
    
    try:
        # Démonstration sur les 2 systèmes
        demo_train_ticket()
        demo_online_boutique()
        
        # Statistiques finales
        demo_statistiques()
        
        # Conclusion
        bandeau("FIN DE LA DÉMONSTRATION")
        print("\n  ✓ Pipeline fonctionnel sur les 2 systèmes")
        print("  ✓ Détection multi-modale opérationnelle")
        print("  ✓ Alertes enregistrées dans alertes.json")
        print("\n  Pour aller plus loin :")
        print("    • API REST  : uvicorn api.main:app --reload")
        print("    • Dashboard : streamlit run dashboard/app.py")
        print()
    
    except Exception as e:
        print(f"\n❌ Erreur : {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()