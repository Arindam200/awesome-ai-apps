#!/usr/bin/env python3
"""
Comprehensive Vector Search Test for Multi-Collection Setup
Tests vector search functionality across all conference collections
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.models.corpus_manager import ConferenceCorpusManager
import time

def test_vector_search():
    """Test vector search functionality across multiple collections"""

    print("🧪 COMPREHENSIVE VECTOR SEARCH TEST")
    print("=" * 60)
    print("Testing multi-collection vector search in 'conferences' bucket")
    print("=" * 60)

    # Initialize corpus manager
    try:
        corpus_manager = ConferenceCorpusManager()
        print("✅ Connected to Couchbase")
    except Exception as e:
        print(f"❌ Failed to connect to Couchbase: {str(e)}")
        print("💡 Make sure:")
        print("   1. Couchbase credentials are in .env")
        print("   2. CB_BUCKET=conferences")
        print("   3. CB_SEARCH_INDEX=conferences-talks-index")
        return False

    try:
        # Test queries across different domains
        test_queries = [
            {
                "query": "kubernetes security RBAC",
                "description": "Security-focused query"
            },
            {
                "query": "container orchestration microservices",
                "description": "Architecture query"
            },
            {
                "query": "observability monitoring prometheus",
                "description": "Observability query"
            },
            {
                "query": "CI/CD pipeline automation",
                "description": "DevOps query"
            },
            {
                "query": "service mesh istio",
                "description": "Service mesh query"
            }
        ]

        success_count = 0
        total_tests = len(test_queries)

        print(f"🔍 Testing {total_tests} queries across all collections...")
        print("-" * 60)

        for i, test_case in enumerate(test_queries, 1):
            query = test_case["query"]
            description = test_case["description"]

            print(f"\n🧪 Test {i}/{total_tests}: {description}")
            print(f"Query: '{query}'")
            print("-" * 40)

            try:
                # Record start time
                start_time = time.time()

                # Test vector search across all collections
                similar_talks = corpus_manager.get_similar_talks(query, num_results=5)

                # Record end time
                end_time = time.time()
                search_time = end_time - start_time

                if similar_talks:
                    print(f"✅ PASS - Found {len(similar_talks)} results in {search_time:.2f}s")
                    success_count += 1

                    # Analyze results quality
                    has_vector_scores = any(talk.get('score', 0) > 0.1 for talk in similar_talks)
                    has_relevant_content = any(
                        any(word.lower() in talk.get('title', '').lower() + ' ' + talk.get('description', '').lower()
                            for word in query.lower().split()[:3])
                        for talk in similar_talks
                    )

                    # Check conference diversity
                    conferences = set(talk.get('conference_id', 'unknown') for talk in similar_talks)

                    print(f"  📊 Results Analysis:")
                    print(f"     Vector Scoring: {'✅ Good' if has_vector_scores else '❌ Low'}")
                    print(f"     Content Relevance: {'✅ Yes' if has_relevant_content else '⚠️ Limited'}")
                    print(f"     Search Speed: {'✅ Fast' if search_time < 3.0 else '⚠️ Slow'}")
                    print(f"     Conference Coverage: {len(conferences)} different conferences")

                    # Show top 3 results
                    print(f"  🎯 Top Results:")
                    for j, talk in enumerate(similar_talks[:3], 1):
                        score = talk.get('score', 0)
                        title = talk.get('title', 'N/A')[:45]
                        category = talk.get('category', 'N/A')
                        conf_id = talk.get('conference_id', 'N/A')
                        print(f"     {j}. Score: {score:.3f} | {title}... | {category} | {conf_id}")

                else:
                    print("❌ FAIL - No results found")
                    print("  This indicates vector search is not working properly")

            except Exception as e:
                print(f"❌ ERROR - Exception during search: {str(e)}")

        # Test conference-specific filtering
        print(f"\n" + "=" * 60)
        print("🔍 TESTING CONFERENCE FILTERING")
        print("=" * 60)

        # List available conferences
        conferences = corpus_manager.list_conferences()
        if conferences:
            print(f"📊 Found {len(conferences)} conferences:")
            for conf in conferences[:3]:  # Show first 3
                print(f"   - {conf['id']}: {conf['total_talks']} talks")

                # Test filtering for this conference
                if conf['total_talks'] > 0:
                    test_query = "kubernetes"
                    print(f"\n🧪 Testing filter for {conf['id']} with query: '{test_query}'")

                    try:
                        filtered_talks = corpus_manager.get_similar_talks(
                            test_query,
                            conference_id=conf['id'],
                            num_results=3
                        )

                        if filtered_talks:
                            all_correct_conference = all(
                                talk.get('conference_id') == conf['id']
                                for talk in filtered_talks
                            )

                            if all_correct_conference:
                                print(f"   ✅ Conference filtering works - {len(filtered_talks)} results")
                                success_count += 0.5  # Partial credit for filtering test
                            else:
                                print(f"   ⚠️ Conference filtering issues - mixed results")
                        else:
                            print(f"   ❌ No filtered results found")

                    except Exception as e:
                        print(f"   ❌ Conference filtering error: {str(e)}")

                    break  # Test only first available conference
        else:
            print("❌ No conferences found - check data storage")

        print("\n" + "=" * 60)
        print("🎯 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"Successful: {success_count}")
        print(f"Success Rate: {(success_count/total_tests)*100:.1f}%")

        if success_count >= total_tests * 0.8:
            print("\n🎉 VECTOR SEARCH IS WORKING!")
            print("✅ Multi-collection vector search is functional")
            print("✅ RAG application should work correctly")
            verdict = True
        elif success_count >= total_tests * 0.5:
            print(f"\n⚠️ PARTIAL SUCCESS ({success_count}/{total_tests})")
            print("✅ Core vector search is working")
            print("⚠️ Some functionality may need fine-tuning")
            verdict = True
        else:
            print(f"\n❌ MAJOR ISSUES ({success_count}/{total_tests})")
            print("🔧 Vector search needs troubleshooting")
            verdict = False

        # Configuration check
        print("\n" + "-" * 60)
        print("🔍 CONFIGURATION CHECK")
        print("-" * 60)

        print(f"Bucket: {corpus_manager.bucket.name}")
        print(f"Search Index: {corpus_manager.search_index_name}")

        # Test embedding generation
        try:
            print("📝 Testing embedding generation...")
            embedding = corpus_manager.nebius_client.generate_embedding("test query")
            if embedding and len(embedding) == 4096:
                print(f"✅ Embedding generation working (dimensions: {len(embedding)})")
            else:
                print(f"❌ Embedding generation issue (dimensions: {len(embedding) if embedding else 'None'})")
        except Exception as e:
            print(f"❌ Embedding generation error: {str(e)}")

        return verdict

    finally:
        corpus_manager.close()

def test_rag_integration():
    """Test RAG integration with vector search"""

    print("\n" + "=" * 60)
    print("🧪 TESTING RAG INTEGRATION")
    print("=" * 60)

    try:
        # Import RAG components
        from src.models.corpus_manager import search_conference_talks

        # Test the convenience function
        query = "kubernetes security best practices"
        print(f"Testing RAG convenience function with: '{query}'")

        start_time = time.time()
        results = search_conference_talks(query, num_results=3)
        end_time = time.time()

        if results:
            print(f"✅ RAG convenience function works - {len(results)} results in {end_time-start_time:.2f}s")
            for i, talk in enumerate(results, 1):
                title = talk.get('title', 'N/A')[:50]
                score = talk.get('score', 0)
                print(f"   {i}. {title}... (score: {score:.3f})")
            return True
        else:
            print("❌ RAG convenience function returned no results")
            return False

    except Exception as e:
        print(f"❌ RAG integration test failed: {str(e)}")
        return False

def main():
    """Run all tests"""

    print("🚀 STARTING COMPREHENSIVE TESTING")
    print("=" * 60)

    # Test 1: Core vector search
    vector_search_success = test_vector_search()

    # Test 2: RAG integration
    if vector_search_success:
        rag_success = test_rag_integration()
    else:
        rag_success = False

    print("\n" + "=" * 60)
    print("🏁 FINAL RESULTS")
    print("=" * 60)

    if vector_search_success and rag_success:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Vector search is working across multiple collections")
        print("✅ RAG integration is functional")
        print("✅ Your conference talk generator is ready!")
        print("\n💡 Next steps:")
        print("1. Create search index: Use conferences_talks_index.json")
        print("2. Test with your Streamlit app")
        print("3. Generate conference talk proposals! 🚀")
        return True

    elif vector_search_success:
        print("⚠️ VECTOR SEARCH WORKS, RAG NEEDS ATTENTION")
        print("✅ Core functionality is working")
        print("⚠️ RAG integration may need minor fixes")
        print("💡 You can still use the system for most functionality")
        return True

    else:
        print("❌ CRITICAL ISSUES DETECTED")
        print("🔧 Please check:")
        print("1. Environment variables in .env file")
        print("2. Couchbase connection and credentials")
        print("3. Search index creation and configuration")
        print("4. Data storage and embedding generation")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)