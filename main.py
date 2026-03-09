"""
CLI entry point for the Autonomous Blog Writing Agent.

Usage:
    python main.py --topic "Introduction to Transformer Architecture"
"""

from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Generate a technical blog post using an AI agent pipeline."
    )
    parser.add_argument(
        "--topic",
        type=str,
        required=True,
        help="The blog topic to write about.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(name)-30s  %(levelname)-8s  %(message)s",
    )
    logger = logging.getLogger("blog_agent")

    logger.info("=== Autonomous Blog Agent ===")
    logger.info("Topic: %s", args.topic)

    # Build and run the pipeline
    from blog_agent.graph.pipeline import build_graph
    from blog_agent.state import make_initial_state

    app = build_graph()
    initial_state = make_initial_state(args.topic)

    logger.info("Running pipeline...")
    result = app.invoke(initial_state)

    final_md = result.get("final", "")
    if final_md:
        logger.info("Blog generated successfully! (%d chars)", len(final_md))
        print("\n" + "=" * 60)
        print(final_md[:500] + ("..." if len(final_md) > 500 else ""))
        print("=" * 60)
        print(f"\nFull blog saved to the output/ directory.")
    else:
        logger.error("Pipeline completed but no output was produced.")
        sys.exit(1)


if __name__ == "__main__":
    main()
