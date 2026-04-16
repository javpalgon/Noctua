import asyncio

from app.services.graph_qa import qa_service

async def main():
    # Usa un client_id REAL que exista en tus nodos de Neo4j
    client_id = "1d3e8682-d10f-4153-875d-f4a64f31b360"  # ID cliente de Premier padel
    question = "Quien es Ariana Sanchez"
    company_name = "Premier Padel"

    print(f"Preguntando al grafo del cliente {client_id}: {question!r}")
    result = qa_service.process_question(question, client_id, company_name)

    print("\n=== RESULTADO RAW ===")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())