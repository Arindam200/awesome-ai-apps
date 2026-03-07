package session

import "silicon-casino/internal/agentgateway"

type Service struct {
	coord *agentgateway.Coordinator
}

func NewService(coord *agentgateway.Coordinator) *Service {
	return &Service{coord: coord}
}

func (s *Service) FindTableByAgent(agentID string) (*AgentTable, error) {
	if agentID == "" {
		return nil, ErrInvalidRequest
	}
	tableID, roomID, ok := s.coord.FindTableByAgent(agentID)
	if !ok {
		return nil, ErrTableNotFound
	}
	return &AgentTable{AgentID: agentID, RoomID: roomID, TableID: tableID}, nil
}
