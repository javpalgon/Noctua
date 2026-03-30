import asyncio

from app.services.graph_qa import qa_service

async def main():
    # Usa un client_id REAL que exista en tus nodos de Neo4j
    client_id = "29cc6f15-7627-4045-a026-2325fc3f3d97"  # ID cliente del Moon

    question = "Quién es javier leal"  

    print(f"Preguntando al grafo del cliente {client_id}: {question!r}")
    result = qa_service.process_question(question, client_id)

    print("\n=== RESULTADO RAW ===")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())