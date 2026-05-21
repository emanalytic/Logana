from logana.analytics.errorClusterer import StreamingErrorClusterer
from helpers.eventFactory import buildLogEvent


def test_errorClustererMergesSimilarMessages():
    clusterer = StreamingErrorClusterer(maxClusters=3, similarityThreshold=0.6)
    clusterer.ingest(buildLogEvent(logLevel="ERROR", message="Connection failed to database 192.168.1.100"))
    clusterer.ingest(buildLogEvent(logLevel="ERROR", message="Connection failed to database 192.168.1.102"))
    assert len(clusterer.clusters) == 1
    assert clusterer.clusters[0].count == 2


def test_errorClustererSplitsDistinctPatterns():
    clusterer = StreamingErrorClusterer(maxClusters=3, similarityThreshold=0.6)
    clusterer.ingest(buildLogEvent(logLevel="ERROR", message="Connection failed to database"))
    clusterer.ingest(buildLogEvent(logLevel="ERROR", message="NullPointerException in UserService line 42"))
    assert len(clusterer.clusters) == 2
