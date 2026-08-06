import unittest

from src.llm.example_retriever import (
    TranslationExample,
    VerifiedExampleRetriever,
    extract_structural_features,
)


CURRENT = """
class Ping(pong: ActorRef) extends Actor {
  var count = 0
  def receive = {
    case StartMessage => pong ! PingMessage
    case PongMessage => count += 1; if (count >= 10) sender() ! StopMessage
  }
}
class Pong extends Actor {
  def receive = { case PingMessage => sender() ! PongMessage }
}
"""


def example(
    example_id: str,
    source: str,
    *,
    family: str,
    verified: bool = True,
) -> TranslationExample:
    return TranslationExample(
        example_id=example_id,
        akka_source=source,
        rebeca_source=f"reactiveclass {example_id}(10) {{}}\nmain {{}}",
        features=extract_structural_features(source),
        benchmark_family=family,
        syntax_verified=verified,
        semantic_verified=verified,
    )


class VerifiedExampleRetrieverTests(unittest.TestCase):
    def test_excludes_same_family_and_unverified_examples(self) -> None:
        same_family = example("same", CURRENT.replace("Ping", "Alpha"), family="ping_pong")
        unverified = example(
            "unverified",
            "class Counter extends Actor { var n = 0 }",
            family="counter",
            verified=False,
        )
        eligible = example(
            "eligible",
            """class Client(server: ActorRef) extends Actor {
            var retries = 0
            def receive = { case Reply => retries += 1; sender() ! Request }
            }
            class Server extends Actor { def receive = { case Request => sender() ! Reply } }
            """,
            family="request_reply",
        )
        retriever = VerifiedExampleRetriever(
            [same_family, unverified, eligible], top_k=3
        )

        selected, manifest = retriever.retrieve(
            CURRENT, benchmark="simple_ping_pong"
        )

        self.assertEqual([item.example.example_id for item in selected], ["eligible"])
        reasons = {item["example_id"]: item["reason"] for item in manifest["excluded"]}
        self.assertEqual(reasons["same"], "same_benchmark_family")
        self.assertEqual(reasons["unverified"], "not_syntax_and_semantic_verified")
        self.assertFalse(manifest["benchmark_oracle_exposed"])

    def test_prompt_format_contains_only_selected_examples(self) -> None:
        eligible = example(
            "counter_reply_01",
            "class Client(server: ActorRef) extends Actor { var count = 0 }",
            family="client_server",
        )
        retriever = VerifiedExampleRetriever([eligible], top_k=1)
        selected, _ = retriever.retrieve(CURRENT, benchmark="simple_ping_pong")

        rendered = retriever.format_for_prompt(selected)

        self.assertIn('id="counter_reply_01"', rendered)
        self.assertIn("<verified_rebeca_translation>", rendered)


if __name__ == "__main__":
    unittest.main()
